---
title: "Path A: Strands on AgentCore Runtime"
weight: 10
---

This is the **managed-everything path**. You deploy a Strands Python agent into AgentCore Runtime with the AgentCore CLI (`@aws/agentcore`); the Runtime sidecar emits OTEL traces and logs on your behalf. Your only job is to `agentcore deploy` the agent, then deploy the observability CFN with the right `service.name`.

## What You'll Build: Observability

By the end of this path, every agent invocation produces:

- **Traces in X-Ray**: exported automatically by the Runtime sidecar
- **Log events in CloudWatch**: the canonical `invoke_agent` record (sidecar emits this for you)
- **Spans in the GenAI Observability dashboard**: visible under your agent's `service.name`

No evaluation scores yet: Module 2 adds automated LLM-judge scoring on top of this foundation.

## What you'll do

1. **Path A.1 What you'll build**: see the architecture and how the Runtime sidecar replaces the OTEL plumbing you'd otherwise write.
2. **Path A.2 Deploy the agent**: `agentcore deploy` with the AgentCore CLI. ~5 min. Discover the auto-generated `service.name`.
3. **Path A.3 Deploy `agentcore-observability.yaml`**: deploy the observability infrastructure (Transaction Search + log group + index policy). ~3 min.
4. **Path A.4 Invoke and verify**: ask the agent a Luminara question; verify traces in X-Ray and log events in CloudWatch. ~5 min.
5. **Path A.5 Recap & what's next**: what you wired up and how it compares to Path B.

## When this path is right for you

- You already build with Strands.
- You have AWS-managed observability requirements (compliance, central monitoring).
- You don't want to operate a long-lived compute layer for the agent.

If your agent isn't built on Strands, use **[Path B](../path-b-any-framework/)** instead.

## Time

~20 minutes.

::children
