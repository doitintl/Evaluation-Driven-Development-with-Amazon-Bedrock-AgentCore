---
title: "1. Agentic Observability"
weight: 20
---

## The problem

You have an agent in production. Users are talking to it. But you cannot see what it is doing, which tools it called, what reasoning path it took, whether it hallucinated, or why a session took 40 seconds instead of 4. Without observability, every support ticket becomes archaeology: sifting through application logs hoping to reconstruct what happened.

**This module fixes that.** By the end, every invocation of your agent will produce:

- **Traces in [AWS X-Ray](https://docs.aws.amazon.com/xray/latest/devguide/aws-xray.html)**: the full tree of **spans** (each a timed unit of work) from request to response, including every tool call.
- **Records in CloudWatch**: the canonical agent record with input, output, and session context.
- **Spans in the GenAI Observability dashboard**: a purpose-built view for agent trajectories.

No evaluation scores yet. Module 2 adds automated LLM-as-Judge scoring on top of the telemetry foundation you build here.

## Pick your path

Right now your agent runs as an ordinary process on the Code Editor EC2 instance,
the way Module 0 ran it. The two paths differ in **where the agent ends up**:

- **Path A moves it onto managed infrastructure** (AgentCore Runtime), which is
  closer to how you would actually host a production agent, and gets telemetry
  from an injected **sidecar**, a helper process that runs beside your agent and
  handles telemetry so your code does not have to.
- **Path B leaves it exactly where it is** and instruments it by hand, which is
  what you do when you host the compute yourself.

Both produce the same evaluation-ready telemetry, and neither is the toy option.
Pick on one question: **does your agent use the Strands Agents SDK?**

| | Path | Agent framework | How you wire it up | Time |
|---|---|---|---|---|
| **A** | [Strands on AgentCore Runtime](path-a-strands/) | Strands (Python) | Deploy to AgentCore Runtime: the managed sidecar emits OTEL for you, zero instrumentation code | ~20 min |
| **B** | [Any other framework](path-b-any-framework/) | Anything else (this workshop uses **pi-mono**, a TypeScript framework) | Add a small OpenInference adapter that maps your agent's lifecycle events to OpenTelemetry spans | ~45 min |

**Choose Path A** if you build on Strands and want the path of least friction: AgentCore Runtime's sidecar handles all the telemetry.

**Choose Path B** if you build on anything else: LangGraph, CrewAI, a custom in-house framework, or (as in this workshop) pi-mono. You'll instrument the agent with **OpenInference**, an open semantic-convention standard that AgentCore Observability and Evaluation both understand.

:::alert{type="info" header="About Path B and pi-mono"}
This workshop's example agent is built on **pi-mono**, a TypeScript agent framework, so Path B is written against it concretely: real files, real commands you can copy-paste. The *technique* (subscribe to your agent's lifecycle events → emit OpenInference spans → SigV4-sign to AWS) is framework-agnostic. Throughout Path B you'll see **"➡️ For your framework"** notes calling out exactly what changes if your agent isn't pi-mono.
:::

Both paths converge to the identical result: traces in X-Ray, agent records in CloudWatch, spans in the GenAI Observability dashboard, all **evaluation-ready**: so Modules 2, 3, and 4 work the same regardless of which path you took.

## What every path does

1. **Overview**: a one-page picture of what you are about to build.
2. **Deploy observability infrastructure**: a lightweight CloudFormation stack that creates Transaction Search wiring plus index policies on the agent's **log group** (the container CloudWatch stores log records in).
3. **Wire up the agent**: from "deploy a Runtime" (Path A) to "add an OpenInference adapter" (Path B).
4. **Invoke and verify**: run the agent, confirm traces appear in X-Ray, records land in CloudWatch, and spans show in the GenAI Observability dashboard.
5. **Summary**: recap and what comes next.

## What comes next

Once you can see your agent's behaviour (this module), Module 2 teaches you how to **score** it automatically using AgentCore Online Evaluations. The observability infrastructure you deploy here is the foundation that evaluation builds on.

::children
