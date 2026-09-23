---
name: "byo-agentcore-evaluation"
displayName: "BYO AgentCore Observability + Online Evaluation"
description: "Wire any agent (running outside AgentCore Runtime) into AgentCore Observability and Online Evaluation. Primary pattern: an in-process OpenInference adapter (AGENT/LLM/TOOL spans, scope openinference.instrumentation.*) that is natively evaluation-ready. Alternative pattern: the ADOT wrapper + InvokeAgentLogEmitter for subprocess/Python agents. Covers the service-name convention, the Online Evaluation Config schema, and step-by-step failure localization."
keywords: ["agentcore", "byo", "otel", "openinference", "adot", "observability", "online-evaluation", "invoke-agent", "log-emitter", "sigv4"]
author: "EDD Workshop Team"
---

# BYO AgentCore Observability + Online Evaluation

## Overview

This power teaches a coding agent (Kiro / Claude Code / Cursor / etc.) to wire any agent that runs OUTSIDE AgentCore Runtime into AgentCore Observability and Online Evaluation.

There are **two implementation patterns**, and picking the right one is the first decision:

| Pattern | What it is | Use when | Reference implementation |
| --- | --- | --- | --- |
| **A. OpenInference adapter** (primary — what Module 1 Path B builds) | An in-process adapter that maps the agent's lifecycle events to OpenInference spans (`AGENT` / `LLM` / `TOOL`) under a single `openinference.instrumentation.*` tracer scope, SigV4-signed to the X-Ray OTLP endpoint. AgentCore Evaluation natively scores these spans — **no separate log event is needed**. | Your agent runs in-process in a language with an OTEL SDK (TypeScript, Python, Java, Go) and exposes lifecycle hooks (callbacks, middleware, event subscription). | `solutions/module-1/agentcore-trajectory-adapter/` (TypeScript, pi-mono) |
| **B. ADOT wrapper + `InvokeAgentLogEmitter`** (alternative) | Auto-instrument with `aws-opentelemetry-distro` and add a SpanProcessor that emits one canonical `invoke_agent` log record per session into the agent's runtime log group. | Your agent is a Python CLI/subprocess you can wrap with `opentelemetry-instrument`, or you cannot add an in-process adapter. | `travel-agent/otel-wrapper/` (Python) |

Both patterns share the same foundations: a canonical `service.name`, the runtimes log group + field-index policy, the eval-execution IAM role, and the Online Evaluation Config. This Power covers the shared foundations once, then each pattern's specifics, then a verification + failure-localization procedure.

It is the natural complement to `edd-driven-agent-dev` ([`../edd-driven-agent-dev/POWER.md`](../edd-driven-agent-dev/POWER.md)). This Power teaches **wire-up**; the other teaches **what to evaluate and how to triage regressions**.

## When to apply this Power

- A new agent is added to a service and needs the same observability/evaluation surface as the rest of the fleet.
- An existing agent runs on ECS / EC2 / Lambda / locally and you want continuous LLM-as-Judge scoring.
- You added a new specialist tool to an agent and need its calls to show up as nested `TOOL` spans alongside the existing tools.

## The shared foundations (both patterns)

### 1. Pick a `service.name`

The service name is the join key across the entire pipeline:

- It is the `service.name` value in the OTEL resource attributes.
- It names the CloudWatch log group: `/aws/bedrock-agentcore/runtimes/<service.name>` (set as the `aws.log.group.names` resource attribute in Pattern A; the log-event destination in Pattern B).
- It is the entry under `dataSourceConfig.cloudWatchLogs.serviceNames` in the Online Evaluation Config.

Constraints: kebab-case or snake_case (no slashes, dots, or spaces); one service.name per agent (multiple agents → one config each). Example: `travel-agent-edd-workshop`.

### 2. The runtimes log group + field-index policy

```bash
aws logs create-log-group \
  --log-group-name /aws/bedrock-agentcore/runtimes/<service.name> \
  --region us-east-1

aws logs put-index-policy \
  --log-group-identifier "arn:aws:logs:us-east-1:<account>:log-group:/aws/bedrock-agentcore/runtimes/<service.name>" \
  --policy-document '{"Fields":["resource.attributes.service.name","attributes.session.id"]}' \
  --region us-east-1
```

The index policy is mandatory (verified empirically). Without it, AgentCore Online Eval cannot resolve `serviceNames` to per-session events, and no sessions get scored. In the workshop this is provisioned by `cfn/agentcore-observability.yaml`; account-level Transaction Search (X-Ray destination + `aws/spans` log group) must also be enabled once per account, which the same template does.

### 3. The eval-execution IAM role

The role AgentCore Online Eval assumes to read your telemetry and invoke the judge model:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadAgentLogs",
      "Effect": "Allow",
      "Action": [
        "logs:DescribeLogGroups", "logs:DescribeLogStreams",
        "logs:FilterLogEvents", "logs:GetLogEvents",
        "logs:StartQuery", "logs:GetQueryResults",
        "cloudwatch:GenerateQuery", "cloudwatch:GenerateQueryResultsSummary"
      ],
      "Resource": "*"
    },
    {
      "Sid": "WriteEvalResults",
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:us-east-1:<account>:log-group:/aws/bedrock-agentcore/evaluations/*"
    },
    {
      "Sid": "InvokeJudgeModel",
      "Effect": "Allow",
      "Action": "bedrock:*",
      "Resource": "*"
    }
  ]
}
```

Trust policy MUST use principal `bedrock-agentcore.amazonaws.com` (NOT `bedrock.amazonaws.com` — the misnamed principal triggers `AccessDenied` on `CreateOnlineEvaluationConfig` pre-flight) and MUST include the source conditions:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
    "Action": "sts:AssumeRole",
    "Condition": {
      "StringEquals": {
        "aws:SourceAccount": "<account>",
        "aws:ResourceAccount": "<account>"
      },
      "ArnLike": {
        "aws:SourceArn": [
          "arn:aws:bedrock-agentcore:us-east-1:<account>:evaluator/*",
          "arn:aws:bedrock-agentcore:us-east-1:<account>:online-evaluation-config/*"
        ]
      }
    }
  }]
}
```

### 4. The Online Evaluation Config

```python
import boto3
client = boto3.Session(region_name="us-east-1").client("bedrock-agentcore-control")

response = client.create_online_evaluation_config(
    onlineEvaluationConfigName="my_config",  # no hyphens in user-supplied part
    rule={
        "samplingConfig": {"samplingPercentage": 100.0},
        "sessionConfig": {"sessionTimeoutMinutes": 5},
    },
    dataSourceConfig={
        "cloudWatchLogs": {
            "logGroupNames": ["/aws/bedrock-agentcore/runtimes/<service.name>"],
            "serviceNames": ["<service.name>"],
        }
    },
    evaluators=[{"evaluatorId": "Builtin.Helpfulness"}],   # or your custom evaluator id
    evaluationExecutionRoleArn="arn:aws:iam::<account>:role/<role-name>",
    enableOnCreate=True,
)
```

Constraints:

- `onlineEvaluationConfigName` must match `^[a-zA-Z][a-zA-Z0-9_]{0,47}$` — no hyphens, dots, or slashes (the API auto-appends a `-<10char>` suffix that does have a hyphen).
- `serviceNames` MUST match the OTEL `service.name` exactly.
- `enableOnCreate=True` enables scoring immediately; sessions older than `createdAt` are NOT scored.
- In the workshop this is provisioned by `cfn/agentcore-eval-and-obs.yaml` (the `eval_provisioner` Lambda makes this exact call).

## Pattern A: the OpenInference adapter (primary)

The adapter subscribes to the agent's lifecycle events and maps them to three OpenInference span kinds under ONE tracer scope. AgentCore Evaluation natively supports the `openinference.instrumentation.*` scope family: the same spans that populate the GenAI Observability dashboard are what the evaluator scores. No second scope, no framework impersonation, no separately-emitted log event.

The contract (framework-agnostic — only the event plumbing changes per framework):

| Lifecycle moment | Span kind | Span name | Key attributes |
| --- | --- | --- | --- |
| agent start/end | `AGENT` (root) | `invoke_agent <agentName>` | `openinference.span.kind=AGENT`, `session.id`, `input.value` (user query), `output.value` (final answer) |
| LLM call start/end | `LLM` | `llm-call-<n>` | `openinference.span.kind=LLM`, `llm.model_name`, `llm.token_count.*`, `llm.input_messages` / `llm.output_messages` |
| tool execution start/end | `TOOL` | `execute_tool <toolName>` | `openinference.span.kind=TOOL`, `tool.name`, `gen_ai.tool.name`, `input.value` (args), `output.value` (result) |

Wiring rules:

- Single tracer scope named `openinference.instrumentation.<framework>` (e.g. `openinference.instrumentation.pi-mono`).
- Resource attributes: `service.name=<service.name>`, `aws.log.group.names=/aws/bedrock-agentcore/runtimes/<service.name>`, `aws.service.type=gen_ai_agent`.
- Export spans via OTLP http/protobuf to `https://xray.<region>.amazonaws.com/v1/traces`, SigV4-signed (in Node, sign explicitly with `@aws-sdk/signature-v4`; reference exporter in `solutions/module-1/agentcore-trajectory-adapter/`).
- The `TOOL` span's `input.value`/`output.value` are what enable `ToolParameterAccuracy`/`Faithfulness`-style evaluators; the `AGENT` span's `input.value`/`output.value` give the judge the user prompt and final answer. Skimp on these and scores get shallow.

**Adding a new specialist tool requires NO adapter change.** The adapter hooks tool-execution lifecycle events generically, so a newly registered tool automatically emits `execute_tool <newToolName>` spans. That is the point of this pattern: wire-up once, every future tool inherits it.

## Pattern B: ADOT wrapper + `InvokeAgentLogEmitter` (alternative)

For Python agents you can wrap with `opentelemetry-instrument` (or any agent where an in-process adapter isn't feasible). Reference: `travel-agent/otel-wrapper/`.

Six ADOT environment variables, sourced BEFORE `opentelemetry-instrument` runs (a `run.sh` that sources `.env` first; setting them after `import opentelemetry` is too late):

```bash
OTEL_PYTHON_DISTRO=aws_distro
OTEL_PYTHON_CONFIGURATOR=aws_configurator
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_TRACES_EXPORTER=otlp
OTEL_LOGS_EXPORTER=otlp
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=https://xray.us-east-1.amazonaws.com/v1/traces
OTEL_EXPORTER_OTLP_LOGS_ENDPOINT=https://logs.us-east-1.amazonaws.com/v1/logs
OTEL_RESOURCE_ATTRIBUTES=service.name=<service.name>,aws.log.group.names=/aws/bedrock-agentcore/runtimes/<service.name>,aws.service.type=gen_ai_agent
OTEL_EXPORTER_OTLP_LOGS_HEADERS=x-aws-log-group=/aws/bedrock-agentcore/runtimes/<service.name>,x-aws-log-stream=runtime-logs,x-aws-metric-namespace=bedrock-agentcore
```

The two most-forgotten variables are `OTEL_TRACES_EXPORTER=otlp` and `OTEL_LOGS_EXPORTER=otlp`. Without them, ADOT's `aws_configurator` may leave the `LoggerProvider` as a `ProxyLoggerProvider` and the emitter silently drops every record.

Then add the `InvokeAgentLogEmitter` SpanProcessor (reference: `travel-agent/otel-wrapper/invoke_agent_log_emitter.py`). It watches for the `invoke_agent` span to end and emits ONE log record per session with the asymmetric body:

```python
class InvokeAgentLogEmitter(SpanProcessor):
    def on_end(self, span: ReadableSpan):
        if "invoke_agent" not in (span.name or ""):
            return
        body = {
            "input": {
                "messages": [{"content": {"content": json.dumps([{"text": user_query}])}, "role": "user"}]
            },
            "output": {
                "messages": [{"content": {"message": str(agent_response)[:10000], "finish_reason": "end_turn"}, "role": "assistant"}]
            },
        }
        # emit via otel_logger.emit(...) with attributes:
        #   {"event.name": "strands.telemetry.tracer", "session.id": session_id}
```

The asymmetry is critical: input is a JSON-encoded array **string** at `body.input.messages[0].content.content`; output is a **plain string** at `body.output.messages[0].content.message`. Get it wrong and the evaluator's parser rejects the event with no error — the session simply never gets scored. In this pattern the log record's `attributes.event.name` must be `strands.telemetry.tracer` (the evaluator's filter key for this event shape) and `attributes.session.id` must match the trace baggage value.

## Verify (run after any wire-up, and after adding any new tool)

```bash
# 0. Trigger an agent invocation.
npx tsx src/main.ts "test query"        # (or ./run.sh "test query" for Pattern B)

# 1a. PATTERN A: the spans landed in aws/spans with the right scope + tool names.
aws logs filter-log-events \
  --log-group-name aws/spans \
  --filter-pattern '"openinference.instrumentation"' \
  --start-time $(($(date +%s) * 1000 - 300000)) \
  --max-items 5 --region us-east-1 --query 'events[*].message' --output text | head -50
# For a specific new tool:
#   --filter-pattern '"execute_tool <toolName>"'

# 1b. PATTERN B: the invoke_agent log record landed in the runtimes log group.
aws logs filter-log-events \
  --log-group-name "/aws/bedrock-agentcore/runtimes/<service.name>" \
  --filter-pattern '"strands.telemetry.tracer"' \
  --start-time $(($(date +%s) * 1000 - 60000)) \
  --max-items 3 --region us-east-1 --query 'events[0].message' --output text

# 2. The Online Evaluation Config exists and is ENABLED.
aws bedrock-agentcore-control list-online-evaluation-configs \
  --region us-east-1 \
  --query 'onlineEvaluationConfigs[].{name:onlineEvaluationConfigName,status:status}'

# 3. Wait sessionTimeoutMinutes + judge time (~5-15 min), then check for scores.
aws logs describe-log-groups \
  --log-group-name-prefix "/aws/bedrock-agentcore/evaluations/results/" \
  --region us-east-1 --query 'logGroups[].logGroupName'
aws logs filter-log-events \
  --log-group-name "/aws/bedrock-agentcore/evaluations/results/<config-id>" \
  --filter-pattern '"gen_ai.evaluation"' \
  --start-time $(($(date +%s) * 1000 - 1800000)) \
  --max-items 5 --region us-east-1 --query 'events[*].message' --output text | head -30
```

Note: prefer `--max-items` over `--limit` with these log groups — `--limit` can silently return zero events even when matching events exist.

## Failure localization (which step is wrong)

The healthy state: telemetry lands within ~10 seconds of an invocation; an eval-result record lands within 5–15 minutes of session idle. Localize by which of those is missing:

| Symptom | Where the bug is |
| --- | --- |
| Pattern A: nothing in `aws/spans` | Adapter/export: SigV4 signing, OTLP endpoint, or Transaction Search not enabled account-wide |
| Pattern A: spans exist but no `execute_tool <newTool>` span | Tool not registered with the Coordinator, or the lifecycle hook isn't firing for tools |
| Pattern B: runtimes log group empty | Env vars (esp. `OTEL_LOGS_EXPORTER=otlp`) or the emitter's span-name filter |
| Telemetry exists but eval-results log group never appears | Index policy missing (foundation 2), IAM trust principal/conditions (foundation 3), or config `serviceNames` mismatch (foundation 4) |
| Eval results exist for old sessions but not new ones | Config disabled, or sampling percentage < 100 |
| Eval-result records arrive but carry `error.type: AgentSpanMappingException` ("Failed to parse agent_response from agent-span") instead of a score | The pipeline is healthy — the *session content* wasn't scoreable. The AGENT span's `input.value`/`output.value` were empty or missing (empty user query, agent crashed mid-run, or the adapter never set them). Fix the invocation/adapter and generate a fresh session; the evaluator will not backfill. (Verified live: an empty `USER_QUERY` produces exactly this record.) |
| Pattern B: telemetry + config fine, still no scores | The asymmetric body shape — re-check `content.content` (input, JSON string) vs `content.message` (output, plain string) |

## What this Power tells the coding agent to do, every time

When asked to wire a new agent or specialist tool into AgentCore Observability + Online Eval, the coding agent MUST:

1. Ask which pattern applies (in-process adapter possible → Pattern A; Python subprocess → Pattern B). In the workshop's travel-agent, Pattern A is already wired — a new tool needs only Coordinator registration.
2. Pick or confirm the `service.name` (foundation 1).
3. Pattern A: confirm the adapter covers the agent's lifecycle events and the new tool emits `execute_tool <toolName>` spans. Pattern B: add the six env vars + the emitter with the asymmetric body.
4. Confirm the runtimes log group + index policy exist (foundation 2).
5. Confirm the eval-execution role exists with the correct trust + permissions (foundation 3).
6. Create or update the Online Evaluation Config (foundation 4).
7. Run the Verify sequence above and paste the actual outputs back to the user. If any step is empty, use the failure-localization table before changing code.

## When NOT to use this Power

- Agents running INSIDE AgentCore Runtime: the managed sidecar emits telemetry automatically; you only need foundations 2–4.
- Agents that don't talk to a foundation model: Online Eval expects an LLM-shaped final answer. Wrong tool for non-LLM workloads.

## See also

- `../edd-driven-agent-dev/POWER.md` — what to evaluate + the regression-triage discipline. Apply this Power first (wire-up), then that one (evaluation).
- `solutions/module-1/agentcore-trajectory-adapter/` — Pattern A reference (TypeScript).
- `travel-agent/otel-wrapper/` — Pattern B reference (Python).
- AgentCore evaluators reference: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/evaluations.html
