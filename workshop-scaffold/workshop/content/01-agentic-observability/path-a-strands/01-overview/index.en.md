---
title: "Path A.1 What you'll build"
weight: 10
---

## What you'll build

A Strands Python travel-agent (`travel-agent-strands/`) deployed to **Amazon Bedrock AgentCore Runtime**, with the Runtime's built-in OTEL sidecar emitting traces and the canonical `invoke_agent` log event automatically. You then deploy the eval+obs CloudFormation stack to score every invocation.

![Path A: agentcore deploy packages your Strands agent onto the managed AgentCore Runtime, where an injected OTEL sidecar exports spans to Observability and on to Online Evaluation. You write no telemetry code.](/static/images/diagrams/path-a-architecture.png)

## Why this is the simplest path

The Runtime's OTEL sidecar replaces all the wire-up work Path B has to do:

- The sidecar emits the `invoke_agent` log record with the right asymmetric body shape: for free.
- It propagates `traceId` as the session correlation key automatically.
- It stamps `service.name = <agentName>.<endpoint>` on every record (dot-joined, runtime id dropped). Note the log group keeps the runtime id, so the two strings differ: Path A.2 captures both.
- It SigV4-signs and exports OTLP to AWS endpoints.

**You write zero OTEL code and set zero OTEL env vars.** Your only responsibility is to:

1. `agentcore deploy`: deploy the agent with the AgentCore CLI.
2. Discover **both** auto-generated names from CloudWatch (Path A.2 does this for you).
3. Deploy `cfn/agentcore-observability.yaml` with the **log-group form** of the name
   (`RUNTIME_LOG_SUFFIX`, the one that keeps the runtime id) as the `ServiceName`
   parameter. The dot-joined emitted `service.name` is a separate value, and Module 2 is
   where it comes in.

That's the whole path.

## Why is `service.name` discovered after deploy, not before?

AgentCore Runtime auto-generates `service.name` based on the runtime ID, which only exists *after* `agentcore deploy` succeeds. Hence the unusual order: deploy agent (Path A.2), then deploy observability CFN (Path A.3), instead of the reverse (Path B deploys observability first, then instruments the agent).

Some teams hard-code a `service.name` of their own choosing in `agentcore.json` to break this chicken-and-egg, that's also fine. We chose the auto-generated default here because it matches the AWS doc walk-through.

## What's already on disk

```bash
travel-agent-strands/
├── README.md
├── requirements.txt
├── main.py                       # local CLI (not used by Runtime)
├── agentcore/
│   └── agentcore.json            # AgentCore CLI deploy spec — read this in Path A.2
│                                 # (aws-targets.json is generated on-box during deploy)
├── runtime/
│   └── main.py                   # BedrockAgentCoreApp wrapper Runtime invokes
└── src/                          # the Strands Coordinator + 3 tools
```

Step 02: deploy the agent. Step 03: deploy the eval CFN. Step 04: invoke and verify.
