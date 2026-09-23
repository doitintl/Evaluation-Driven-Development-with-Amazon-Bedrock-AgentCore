---
title: "Path B.1 Overview"
weight: 10
---

## What you'll build

A ~200-line **OpenInference adapter** that subscribes to your agent's lifecycle events and emits three kinds of span to AWS:

| Span kind | One per | Carries |
|---|---|---|
| `AGENT` | invocation | the user query and final answer |
| `LLM` | model inference | model name, token counts, the messages it saw |
| `TOOL` | tool execution | tool name, arguments, result |

You change **nothing** about the agent's logic. The adapter observes it from the outside and SigV4-signs the spans to X-Ray's OTLP endpoint.

:::alert{type="success" header="The one idea to take away: one scope does both jobs"}
The spans you emit for the **dashboard** are the exact spans AgentCore Evaluation **scores** in Module 2. There is no second export, no framework impersonation, no separate log event.

That is why this path is worth the ~45 minutes: instrument once, and both debugging and automated scoring work. When a coding agent adds a 4th tool in Module 4, its calls become `TOOL` spans and get scored automatically, with no adapter change.
:::

## Why plain OpenTelemetry isn't enough

Standard OTEL's `gen_ai.*` namespace has spans for the agent and for tools, but **none for individual model inferences**. So you get a flat, two-level tree:

```
invoke_agent                      ← standard OTEL sees this
├── execute_tool query_sites      ← and these
├── execute_tool plan_route
└── execute_tool suggest_dining
```

You can see *that* the agent called three tools. You cannot see *which model call decided to*, what it was looking at, or what it cost.

OpenInference adds the missing middle layer:

```
invoke_agent                    (AGENT, 41.70s)
├── llm-call-2                  (LLM, 0.90s, 3/77 tokens)      → decides to call query_sites
├── execute_tool query_sites    (TOOL, 0.01s)
├── llm-call-3                  (LLM, 0.85s, 1911/105)         → decides to call plan_route
├── execute_tool plan_route     (TOOL, 0.01s)
├── llm-call-4 to llm-call-8    (LLM, one per model turn)      → each decides the next call
├── execute_tool suggest_dining (TOOL, 0.00s)
└── llm-call-9                  (LLM, 19.53s, 5809/1199)       → final synthesis
```

Now the agent's reasoning is queryable: nine model calls for this run, the slow one is the
synthesis, and the tool-selection calls are cheap by comparison. (Numbering starts at 2
because the very first span belongs to your own prompt; Path B.4 explains it.)

This is what it looks like in CloudWatch once you finish Path B.4, your agent listed with its session and trace counts:

![The CloudWatch GenAI Observability dashboard after Path B, showing the instrumented agent with its session and trace counts](/static/images/1f-genai-dashboard.png)

:::alert{type="info" header="Optional: the full standard-OTEL vs OpenInference comparison"}
| Aspect | Standard OTEL (`gen_ai.*`) | OpenInference |
|---|---|---|
| Span hierarchy | 2 levels | 3 levels (`AGENT` → `LLM` → `TOOL`) |
| LLM calls visible | No, opaque | Yes, one span each |
| Token tracking | None | `llm.token_count.prompt` / `.completion` / `.total` |
| Model attribution | None | `llm.model_name` per call |
| Message content | Final I/O only | `llm.input_messages` + `llm.output_messages` per call |
| Portability | AWS-specific | Also works with Arize Phoenix, Langfuse |

[OpenInference](https://github.com/Arize-ai/openinference) is an open semantic-convention standard, so the same instrumentation works across backends. AWS names it as a supported instrumentation library for non-Strands frameworks in the [AgentCore Observability docs](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html), alongside Openllmetry, OpenLit, and Traceloop.
:::

:::alert{type="info" header="Optional: evidence that AgentCore natively scores this scope"}
Verified against the on-demand Evaluate API: a pi-mono session emitted under `openinference.instrumentation.pi-mono` scores `TrajectoryInOrderMatch`, `ToolParameterAccuracy`, `ToolSelectionAccuracy`, and `Faithfulness`, identically to a first-class framework like Google ADK. The evaluator reads tool names, arguments, results, and the final answer straight from the spans.
:::

:::alert{type="info" header="Plumbing: this workshop uses pi-mono, the technique is framework-agnostic"}
The example agent is **pi-mono** (TypeScript), so every command below is concrete and copy-pasteable. Only one line of the adapter is pi-mono-specific: the import of your agent. Each step carries a **➡️ For your framework** note marking exactly what changes for LangGraph, CrewAI, or a custom agent.
:::

## What you need before starting

- Path B.2 completed (Transaction Search enabled, log groups created)
- The `travel-agent` code, already cloned into the Code Editor
- Node.js 20+ (pre-installed)

**Next: [Path B.2 Deploy observability infrastructure](../02-deploy-obs-cfn/).**
