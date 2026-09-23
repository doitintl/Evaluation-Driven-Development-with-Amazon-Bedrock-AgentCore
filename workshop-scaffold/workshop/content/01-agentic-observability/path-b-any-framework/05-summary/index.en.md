---
title: "Path B.5 Summary"
weight: 50
---

## What you built

Four small files, about 415 lines total, that instrument an agent without touching its logic:

| File | Lines | Purpose |
|---|---|---|
| `sigv4-exporter.ts` | 130 | Signs OTLP requests for X-Ray |
| `otel-setup.ts` | 37 | Wires the tracer to X-Ray, sets `aws.log.group.names` |
| `openinference-adapter.ts` | 180 | Maps agent lifecycle events to `AGENT`/`LLM`/`TOOL` spans |
| `run.ts` | 68 | Entry point |

## What you proved

| Claim | Your evidence |
|---|---|
| The full trajectory is captured | Your `aws/spans` query printed `AGENT=1` plus multiple `LLM` and `TOOL` spans for one run |
| Per-call cost is visible | Token counts on each `LLM` row, with synthesis far more expensive than tool selection |
| The spans are evaluation-ready | Module 2 scores these exact spans, with no second export |
| Your run reached AWS, not someone else's | The `session.id` in the spans matches the one your terminal printed |

:::alert{type="success" header="The transferable rule"}
Observability for agents means capturing the **trajectory**, not just the request and response. Once the trajectory is in spans under a scope AgentCore understands, evaluation comes for free.

Concretely: when a coding agent adds a fourth tool in Module 4, its calls appear as `TOOL` spans and get scored automatically, because the adapter subscribes to *lifecycle events* rather than to named tools.
:::

:::alert{type="info" header="Optional: why standard OTEL could not do this"}
Standard OpenTelemetry's `gen_ai.*` namespace has no semantic convention for individual model inferences. It gives you `invoke_agent` (the whole run) and `execute_tool` (each tool call), but the reasoning steps in between are invisible.

OpenInference fills that gap with `openinference.span.kind: "LLM"`, carrying `llm.model_name`, `llm.token_count.*`, and the input/output messages. The adapter subscribes to pi-mono's `message_start`/`message_end` events and maps each inference to one of those spans. AWS [documents OpenInference](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html) as a supported instrumentation library for non-Strands frameworks.
:::

## Next

- **[Module 2](../../../02-continuous-monitoring/)**: an automated judge scores every session, using the spans you just emitted.
- **Module 3**: trajectory tests that catch regressions before deploy.
- **Module 4**: turn production traffic into fresh test cases.
