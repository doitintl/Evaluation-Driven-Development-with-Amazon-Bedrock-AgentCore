---
title: "Appendix: Other instrumentation approaches"
weight: 90
---

Module 1 gives you two paths: **Path A** (Strands on AgentCore Runtime, telemetry for free) and **Path B** (any other framework via an OpenInference adapter). Those are the two you should use.

This appendix is **reference only**: you don't need it to complete the workshop. It captures two alternative wire-ups that earlier versions of this workshop taught as standalone variants, kept here for teams whose constraints call for them.

---

## A. Strands on plain EC2 / ECS (no AgentCore Runtime)

If you build on Strands but can't deploy to AgentCore Runtime (you run your own EC2, ECS, or k8s), you don't need an adapter at all: Strands' built-in `strands.telemetry` emits the canonical AgentCore records natively. You just point OpenTelemetry at the AWS endpoints with environment variables and launch under `opentelemetry-instrument`.

The wire-up is a `.env` of OTEL variables (activate ADOT, set the OTLP endpoints, route to your log group, and set `service.name`):

```bash
# ADOT activation
export OTEL_PYTHON_DISTRO=aws_distro
export OTEL_PYTHON_CONFIGURATOR=aws_configurator
export OTEL_TRACES_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf

# AWS OTLP endpoints
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=https://xray.us-east-1.amazonaws.com/v1/traces
export OTEL_EXPORTER_OTLP_LOGS_ENDPOINT=https://logs.us-east-1.amazonaws.com/v1/logs

# Route log events to the agent's runtime log group
export OTEL_EXPORTER_OTLP_LOGS_HEADERS=x-aws-log-group=/aws/bedrock-agentcore/runtimes/travel-agent-strands-edd-workshop,x-aws-log-stream=runtime-logs

# Identify the agent
export OTEL_RESOURCE_ATTRIBUTES=service.name=travel-agent-strands-edd-workshop
export AGENT_OBSERVABILITY_ENABLED=true
```

Then run the agent through the instrumentation wrapper:

```bash
opentelemetry-instrument python main.py "Plan a 2-day trip focused on history, arriving Monday"
```

The result is identical to Path A's telemetry, same log group, same records, just without the managed Runtime. The trade-off is that you operate the compute yourself.

---

## B. How the log-event contract works (the BYO bridge, from first principles)

Path B's OpenInference adapter is the production-grade way to instrument a non-Strands agent. But it's worth understanding *what* the adapter is actually satisfying under the hood: the **log-event contract** AgentCore expects.

Historically, before AgentCore Evaluation supported the OpenInference scope family, a non-Strands agent had to *impersonate* Strands: emit an `invoke_agent` span under `strands.telemetry.tracer` **and** a matching CloudWatch log event with a specific "asymmetric body" shape (input as a content list, output as a message string):

```jsonc
{
  "input":  { "messages": [{ "content": { "content": "[{\"text\":\"<user query>\"}]" }, "role": "user" }] },
  "output": { "messages": [{ "content": { "message": "<agent response>", "finish_reason": "end_turn" }, "role": "assistant" }] }
}
```

This is no longer necessary: AgentCore Evaluation now natively reads the trajectory from OpenInference **spans** (that's what Path B relies on, and it's verified working). But the asymmetric-body shape is still useful background if you ever debug how the Strands-native path (Path A) or older integrations represent a session, or if you work with a tool that only emits log events and not spans.

**The takeaway:** whatever your framework, evaluation needs to see (1) the user prompt, (2) the final answer, and (3) the tool calls with their arguments and results. OpenInference spans carry all three, which is why Path B works for any framework without impersonation.
