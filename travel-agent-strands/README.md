# Luminara Travel Agent (Strands port)

Python / [Strands Agents](https://strandsagents.com) port of the pi-mono
TypeScript travel-agent. A single Coordinator agent orchestrates three
specialist tools over the fictional city of Luminara.

This codebase backs **variants 1a (AgentCore Runtime)** and **1b (EC2)** of the
AgentCore Observability + Online Evaluation workshop. The TS pi-mono version in
`../travel-agent/` remains the source of truth for shared shape (system prompt,
tool signatures, mock data).

## Architecture

```
Coordinator (strands.Agent + BedrockModel)
├── @tool query_sites      — attraction lookup (hours, closure days, prices)
├── @tool plan_route       — multi-day itinerary planner with constraint solver
└── @tool suggest_dining   — restaurants near a planned attraction
```

The route planner is deterministic — it ports the pi-mono closure-detection,
priority placement of time-restricted attractions, and greedy nearest-neighbor
schedule fill. Module 4 (model swap pedagogy) depends on this baseline.

## Setup

```bash
cd travel-agent-strands
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then edit if needed
```

Bedrock access in `us-east-1` for `us.anthropic.claude-sonnet-4-6` is required.

## Usage

### Single-shot

```bash
AWS_REGION=us-east-1 python main.py "Plan a 2-day trip focusing on history"
```

### Interactive REPL

```bash
AWS_REGION=us-east-1 python main.py
```

Type `exit` or `quit` (or Ctrl-D) to end the session.

## Layout

```
travel-agent-strands/
├── main.py                  # CLI entry (single-shot + REPL)
├── requirements.txt
├── .env.example
├── runtime/
│   └── agentcore.json       # AgentCore Runtime deploy spec (variant 1a)
└── src/
    ├── coordinator.py       # create_coordinator_agent + system prompt
    ├── agents/
    │   ├── sites_agent.py   # @tool query_sites
    │   ├── route_agent.py   # @tool plan_route
    │   └── dining_agent.py  # @tool suggest_dining
    ├── data/
    │   ├── attractions.py   # mock Luminara attractions
    │   ├── restaurants.py   # mock restaurants
    │   ├── distances.py     # travel-time matrix
    │   └── types.py         # dataclasses for shared shapes
    └── utils/
        ├── config.py        # load_config() — AWS_REGION + MODEL_ID
        └── constraints.py   # closure detection + travel-time helpers
```

## Variants

- **1a — AgentCore Runtime**: see `agentcore/agentcore.json`. Participants run
  `agentcore deploy` (the `@aws/agentcore` CLI) themselves; this repo only
  provides the deploy spec and a `runtime/main.py` wrapper exposing the
  `BedrockAgentCoreApp` entrypoint. The account-specific `agentcore/aws-targets.json`
  is generated on-box during the workshop, not committed.
- **1b — EC2**: run `python main.py "..."` (or the REPL) on an EC2 host with
  `aws-opentelemetry-distro` configured per the workshop's wire-up step. This
  repo intentionally does not author observability env vars or the
  `opentelemetry-instrument` invocation — that is the workshop content.

## Smoke test

```bash
AWS_REGION=us-east-1 python main.py "What is the Grand Museum"
```

Expect a Luminara-grounded reply that mentions hours, the Monday closure, and
the $25 ticket.
