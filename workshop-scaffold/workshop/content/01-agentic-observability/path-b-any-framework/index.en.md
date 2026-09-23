---
title: "Path B: Any framework (OpenInference → AWS)"
weight: 60
---

## Path B: Full LLM Trajectory in AWS GenAI Observability via OpenInference

This path captures the **complete agent trajectory**: every LLM inference call, every tool execution, with per-call token counts and model attribution, and sends it directly to AWS CloudWatch GenAI Observability using **OpenInference semantic conventions**.

**OpenInference is the open standard for instrumenting any agent framework.** The same spans work with AWS, Arize Phoenix, Langfuse, and other backends. This workshop's example agent is built on **pi-mono** (TypeScript), so every step is concrete and copy-pasteable, but the technique is framework-agnostic. Each step includes a **➡️ For your framework** note explaining what changes for LangGraph, CrewAI, a custom agent, and so on.

### Why an Open Convention Instead of Plain OTEL

Standard OpenTelemetry's `gen_ai.*` namespace defines agent-level and tool-level attributes, but it has **no semantic convention for per-LLM-call spans**: individual model inferences are opaque internal work inside the agent span. You can see *that* an agent ran and *which* tools it called, but not *which* model call decided to invoke a tool, how many tokens each decision cost, or where latency concentrated.

**OpenInference** solves this by defining `openinference.span.kind: "LLM"` as a dedicated span type with `llm.model_name`, `llm.token_count.*`, and `llm.input_messages`/`llm.output_messages`. Each model inference becomes a visible, queryable span in the trace tree: alongside `AGENT` and `TOOL` spans.

### One Scope, Both Jobs

AgentCore natively understands the `openinference.instrumentation.*` scope family. The **same spans you emit for the dashboard are the spans AgentCore Evaluation scores** in Module 2: tool names, arguments, results, and the final answer are all read straight from the OpenInference spans. There is no second scope, no framework impersonation, and no separately-exported log event: this path emits **one scope for everything** and is evaluation-ready out of the box.

### When to Use This Path

Choose Path B when your agent is **not** built on Strands and you want:
- Full LLM-call-level trajectory **without running extra infrastructure** (no Docker, no external platform)
- Everything in **one AWS dashboard** (GenAI Observability in CloudWatch)
- An **open, portable standard** (the same OpenInference spans work with Arize Phoenix, Langfuse, AWS, etc.)
- Per-call token counts and model attribution in CloudWatch Transaction Search
- Telemetry that is **evaluation-ready** for Module 2 with no extra work

### Architecture

![Path B: your agent keeps running on the Code Editor EC2. An OpenInference adapter you write turns its lifecycle events into AGENT, LLM and TOOL spans, exports them to the X-Ray OTLP endpoint, and they land in aws/spans for both the dashboard and evaluation.](/static/images/diagrams/path-b-architecture.png)

### Time Estimate

| Step | Duration |
|------|----------|
| Overview | ~5 min |
| Deploy observability CFN | ~10 min (2 to 4 min for the stack, then 6 to 10 min for Transaction Search to reach `ACTIVE`) |
| Build the adapter | ~15 min |
| Run and verify | ~10 min |
| Summary | ~5 min |

**Total: ~45 minutes**, most of the deploy step being an unattended wait you can read ahead during.
