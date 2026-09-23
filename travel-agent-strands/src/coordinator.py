# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Travel-planning coordinator agent — Strands port of coordinator.ts.

The system prompt below mirrors ``COORDINATOR_SYSTEM_PROMPT`` in pi-mono: same
Capabilities, Workflow, Itinerary Format, Handling Modifications and Important
Rules sections, including the "Always invoke query_sites BEFORE plan_route" rule.

One deliberate difference: the TypeScript prompt also opens with an
"ABSOLUTE RULE, NO EXCEPTIONS" block, which is the subject of the Module 3.3
weaken-and-restore exercise. That exercise runs against the TypeScript agent
(`travel-agent/`), so this port does not carry the block. Measured on a live
Runtime deployment, this prompt still drives the full trajectory: a run of the
Path A.4 queries produced query_sites, plan_route and suggest_dining spans.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from strands import Agent
from strands.handlers.callback_handler import null_callback_handler
from strands.models import BedrockModel

from .agents import plan_route, query_sites, suggest_dining
from .utils.config import AppConfig


COORDINATOR_SYSTEM_PROMPT = """You are a travel planning coordinator for the fictional city of Luminara. You help users plan multi-day travel itineraries by orchestrating specialist tools.

## Your Capabilities

You have access to three specialist tools:

1. **query_sites** — Look up attraction information (hours, closure days, prices, booking requirements)
2. **plan_route** — Generate optimized multi-day itineraries respecting constraints (closure days, opening hours, travel time, daily time budget)
3. **suggest_dining** — Recommend restaurants near planned attractions for specific meal types

## Workflow

When a user requests help planning a trip, follow this order:

1. **Clarify** (if needed): If the request is ambiguous, ask at most 2 clarifying questions. Examples:
   - "How many days will you be visiting?"
   - "Are there any must-see attractions or interests (history, art, nature, food)?"
   - "Do you have a preferred start day of the week?"
   Do NOT ask more than 2 questions before producing an itinerary.

2. **Look up attractions**: Use the query_sites tool to gather information about relevant attractions based on the user's interests or request.

3. **Plan the route**: Use the plan_route tool with the selected attractions, number of days, and start day to generate an optimized schedule.

4. **Add dining suggestions**: Use the suggest_dining tool to recommend restaurants for meal breaks at appropriate times, based on which attractions are nearby.

5. **Synthesize**: Combine all specialist outputs into a clear, formatted itinerary for the user.

## Itinerary Format

Present itineraries with this structure:

=== Day N: [DayOfWeek] ===
HH:MM–HH:MM | [Attraction/Restaurant Name] | [visit/meal/travel] | (duration)
[Any notes: booking required, rescheduled due to closure, etc.]

---

**Summary**
- Total attractions: N
- Total days: N
- Estimated cost: $X
- Adjustments: [list any schedule changes due to closures or conflicts]

## Handling Modifications

When a user requests changes to a previously generated itinerary:
- Re-invoke the relevant specialist tools to validate the modification
- If the change creates a conflict (e.g., visiting a closed attraction), explain the issue and suggest alternatives
- Present the updated itinerary in the same format

## Important Rules

- Always invoke query_sites BEFORE plan_route so you have accurate attraction data
- Respect the dependency order: sites → route → dining
- If a specialist tool fails or returns an error, inform the user what capability is unavailable and provide what information you can from other tools
- Never suggest visiting an attraction on a day it is closed
- Always mention if an attraction requires advance booking
- Keep responses focused and actionable — users want itineraries, not essays"""


def create_coordinator_agent(
    config: AppConfig,
    callback_handler: Optional[Callable[..., Any]] = None,
) -> Agent:
    """Build the Luminara travel-planning coordinator agent.

    The returned ``Agent`` is wired with three specialist tools (``query_sites``,
    ``plan_route``, ``suggest_dining``) and the verbatim Coordinator system
    prompt from the pi-mono TypeScript original.

    Args:
        config: Resolved application config containing model id and AWS region.
        callback_handler: Optional callback for streaming output. Pass
            ``strands.handlers.callback_handler.null_callback_handler`` to
            silence interactive streaming (useful for single-shot CLI / runtime
            entry-points where the caller prints the final text).

    Returns:
        A ready-to-invoke ``strands.Agent``.
    """
    model = BedrockModel(
        model_id=config.model_id,
        region_name=config.aws_region,
    )

    kwargs: dict[str, Any] = {
        "model": model,
        "system_prompt": COORDINATOR_SYSTEM_PROMPT,
        "tools": [query_sites, plan_route, suggest_dining],
    }
    if callback_handler is not None:
        kwargs["callback_handler"] = callback_handler

    return Agent(**kwargs)


__all__ = [
    "COORDINATOR_SYSTEM_PROMPT",
    "create_coordinator_agent",
    "null_callback_handler",
]
