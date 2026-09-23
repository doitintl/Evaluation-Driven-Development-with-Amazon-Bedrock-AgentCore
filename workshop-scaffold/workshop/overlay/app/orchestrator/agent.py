"""Orchestrator agent — top-level travel planner.

The orchestrator is itself a Strands agent. It exposes one Strands tool per
sub-agent. Each tool does an HTTP POST to the sub-agent's `/invoke` endpoint.

Why HTTP-as-tool (not A2A protocol) for the workshop:
  - The trace is explicit: each sub-agent call shows up as a named tool span
    on the orchestrator's trace. Trajectory matching gets meaningful tool
    names (`destination_agent`, `flight_agent`, ...).
  - The participant can see exactly what payload moves between agents.
  - No extra A2A dependency surface; smaller surface to teach.

Each sub-agent emits its own OTEL spans (linked to the orchestrator's trace
via the standard W3C `traceparent` header propagated by httpx instrumentation).
The CW GenAI dashboard renders the parent + 5 child invoke_agent spans as a
nested tree.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx
from strands import Agent, tool
from strands.models import BedrockModel

logger = logging.getLogger(__name__)

MODEL_ID = os.environ.get(
    "MODEL_ID", "us.anthropic.claude-sonnet-4-6"
)
SERVICE_NAME = "orchestrator"

# Sub-agent endpoints injected via env at deploy time. Defaults are local
# dev (each sub-agent on its own port).
SUB_AGENT_URLS = {
    "destination_agent": os.environ.get("DESTINATION_AGENT_URL", "http://localhost:8001"),
    "flight_agent":      os.environ.get("FLIGHT_AGENT_URL",      "http://localhost:8002"),
    "train_agent":       os.environ.get("TRAIN_AGENT_URL",       "http://localhost:8003"),
    "hotel_agent":       os.environ.get("HOTEL_AGENT_URL",       "http://localhost:8004"),
    "car_agent":         os.environ.get("CAR_AGENT_URL",         "http://localhost:8005"),
}

_HTTP_TIMEOUT = float(os.environ.get("SUB_AGENT_TIMEOUT_S", "120"))

# Per-orchestrator-invocation buffer of nested sub-agent traces.
# Each entry is one "batch" — the rows returned by a single _call_sub_agent
# call. Stored in the order the orchestrator made the calls, so the shared
# server can pop one batch per orchestrator tool span at attach time.
_PENDING_NESTED: dict[str, list[list[dict]]] = {}


def consume_nested_traces(session_id: str) -> list[list[dict]]:
    """Drain the per-call nested-trace batches for this orchestrator session."""
    return _PENDING_NESTED.pop(session_id, [])


SYSTEM_PROMPT = """You are the Orchestrator agent for a multi-agent travel
booking system. The traveller's goal is a feasible itinerary that respects
their constraints (dates, budget, dietary, no-night-flights, etc.).

You ROUTE work to specialist sub-agents. You do NOT call DDB or Bedrock
directly — you only call the sub-agent tools below.

Sub-agents:
  - destination_agent: places to visit, opening hours, destination bookings.
  - flight_agent:      inter-city flight search and booking.
  - train_agent:       inter-city train search and booking.
  - hotel_agent:       hotel search and booking.
  - car_agent:         private-car booking.

# TODO 2.2.1 — STRENGTHEN THE FIRST RULE.
#
# A customer reported the agent booked WildWildWet on a Monday (closed day).
# The current "Hard rules: 1. ALWAYS call check_destination_open ..." is
# buried in a list and abstract. Rewrite it as an "ABSOLUTE RULE — NO
# EXCEPTIONS" section ABOVE these Hard rules, with concrete worked examples
# (e.g. "User says 'book WildWildWet on 2026-06-08' → first call
# check_destination_open, only proceed if it's open").
#
# After editing, rebuild + roll the deployment (Module 2.2 step 3) and
# re-run the eval. Trajectory should improve on
# sg_constraint_wildwildwet_monday.

Hard rules:
  1. ALWAYS call destination_agent's check_destination_open BEFORE booking
     a destination. (You enforce this by asking destination_agent — never
     skip or assume the destination is open.)
  2. NEVER fabricate flight numbers, hotel IDs, or dates. Use only IDs the
     sub-agents return.
  3. If the user gives a budget, run all your booking proposals against it
     and surface the running total.
  4. If a sub-agent returns a constraint failure (e.g. destination closed
     on requested date), DO NOT silently change plans — explain to the user
     and propose options.

Each tool below takes a single `prompt` string. Phrase the prompt as a
natural-language sub-task (e.g. "Search Singapore→Bali flights on 2026-06-10,
no night flights"). The sub-agent will parse it, call its tools, and return
a text response with the data you need.

Be concise in your final answer. No emoji. Cite the booking IDs you got back.

# TODO 4.1 (optional, Module 4) — ADD A RECOVERY PROTOCOL.
#
# Append a RECOVERY PROTOCOL section that explicitly tells the agent to
# loop through dependent constraint re-checks when a constraint is violated.
# E.g. when a destination is closed on the requested date, the agent must:
#   1. Acknowledge the violation explicitly.
#   2. Propose ONE alternative date.
#   3. RE-VERIFY every dependent constraint (flights for the new date, etc.).
#   4. Stop after 3 iterations and surface the conflict.
#
# After this edit, the recursive_recovery_wildwildwet eval case should pass.
"""


def _call_sub_agent(name: str, prompt: str) -> str:
    """Call a sub-agent over HTTP and capture its tool trace.

    The orchestrator's session.id is read from _BYO_SESSION_ID (set by the
    shared server when the request lands). We pass our session.id through to
    the sub-agent, then store its returned trace so the orchestrator's own
    response can include it.
    """
    url = SUB_AGENT_URLS[name].rstrip("/") + "/invoke"
    parent_session = os.environ.get("_BYO_SESSION_ID", "")
    payload = {"prompt": prompt}
    if parent_session:
        payload["session_id"] = f"{parent_session}::{name}"
    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as e:
        logger.error("Sub-agent %s failed: %s", name, e)
        return f"[{name}] error: {e}"

    if parent_session:
        batch = [{"sub_agent": name, **t} for t in data.get("trace", [])]
        _PENDING_NESTED.setdefault(parent_session, []).append(batch)
    return data.get("response", "")


@tool
def destination_agent(prompt: str) -> str:
    """Ask the Destination sub-agent to handle a destination-related sub-task.

    Use for: listing destinations, checking opening hours, booking destination
    entry tickets. Always check_destination_open BEFORE booking.

    Args:
      prompt: Natural-language sub-task. E.g. "Is WildWildWet open on
        2026-06-08?" or "List Singapore theme parks".
    """
    return _call_sub_agent("destination_agent", prompt)


@tool
def flight_agent(prompt: str) -> str:
    """Ask the Flight sub-agent to search or book a flight.

    Args:
      prompt: Natural-language sub-task. E.g. "Find Singapore→Bali flights
        on 2026-06-10, no night flights" or "Book SQ-001 for 2 passengers".
    """
    return _call_sub_agent("flight_agent", prompt)


@tool
def train_agent(prompt: str) -> str:
    """Ask the Train sub-agent for inter-city trains.

    Args:
      prompt: Natural-language sub-task. E.g. "Trains Singapore→KL on
        2026-06-12".
    """
    return _call_sub_agent("train_agent", prompt)


@tool
def hotel_agent(prompt: str) -> str:
    """Ask the Hotel sub-agent for hotel options or to book a stay.

    Args:
      prompt: Natural-language sub-task. E.g. "Hotels in Singapore for
        2026-06-10 to 2026-06-13, party of 2, mid-range".
    """
    return _call_sub_agent("hotel_agent", prompt)


@tool
def car_agent(prompt: str) -> str:
    """Ask the Car sub-agent for private-car options or to book one.

    Args:
      prompt: Natural-language sub-task. E.g. "Book a private SUV in Bali
        for 2026-06-15, 8 hours, pickup at airport".
    """
    return _call_sub_agent("car_agent", prompt)


def build_agent(session_id: str) -> Agent:
    return Agent(
        model=BedrockModel(model_id=MODEL_ID, temperature=0, max_tokens=4000),
        system_prompt=SYSTEM_PROMPT,
        tools=[destination_agent, flight_agent, train_agent, hotel_agent, car_agent],
        trace_attributes={
            "service.name": SERVICE_NAME,
            "session.id": session_id,
        },
    )
