---
title: "Path A.3 Deploy observability infrastructure"
weight: 30
---

**Scenario.** Your agent runs on Runtime and its sidecar is already trying to emit
telemetry, but the account has nowhere to keep spans yet. **Skip this step and
Module 1 produces no traces, the dashboard stays empty, and Module 2 can never
score anything.** One CloudFormation deploy fixes it, in 2 to 4 minutes.

## What one deploy turns on

```bash
source /workshop/edd-workshop/config.env
cd /workshop/edd-workshop

aws cloudformation deploy \
  --stack-name edd-observability \
  --template-file cfn/agentcore-observability.yaml \
  --parameter-overrides ServiceName=${RUNTIME_LOG_SUFFIX} \
  --capabilities CAPABILITY_IAM \
  --no-fail-on-empty-changeset
```

Wait for `Successfully created/updated stack`.

`${RUNTIME_LOG_SUFFIX}` comes from the script you ran in Path A.2, and `config.env`
supplies it in any terminal. It is the log-group form of the name, which is what
this template needs.

:::alert{type="warning" header="If the deploy fails saying ServiceName is empty"}
`config.env` does not have the value yet. Run Path A.2's capture step:

```bash
cd /workshop/edd-workshop && ./scripts/capture-runtime-names.sh && source config.env
```
:::

:::alert{type="info" header="Learn: what Transaction Search is, and why the dashboard needs it"}
**AWS X-Ray** is the AWS distributed tracing service. It collects spans, the timed
units of work inside a request, and assembles them into a trace showing the call
path. For an agent, that trace *is* the trajectory: which tool ran, in what order,
and how long each took.
[X-Ray documentation](https://docs.aws.amazon.com/xray/latest/devguide/aws-xray.html)

By default X-Ray samples traces and keeps them in its own backend, reachable only
through the X-Ray API. That is fine for latency debugging and useless for
evaluation, which needs every session rather than a sample, and needs to query
them by attribute.

**Transaction Search** changes the destination. Once enabled, X-Ray writes 100% of
spans into a CloudWatch log group named `aws/spans`, as structured records. That
one change is what makes spans queryable by `service.name` and `session.id`, and
it is what both the GenAI Observability dashboard and Module 2's evaluator read.

Without it, the dashboard stays empty and no session can ever be scored.
[Transaction Search documentation](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Transaction-Search.html)

It is an **account-level** setting, not per-agent, so enabling it once covers every
agent in the account.
:::

:::alert{type="info" header="Plumbing: what the stack creates, and why it is a template"}
| Resource | Purpose |
|---|---|
| Transaction Search wiring | Points X-Ray's trace destination at the `aws/spans` log group |
| Log group index policy | Indexes `service.name` and `session.id` so Logs Insights queries stay fast |

There is no native CloudFormation resource for the X-Ray destination API, so a
small Lambda custom resource calls it. Deploying it as a template rather than
clicking it in the console leaves you something you can take back to your own
account.

The stack does **not** create the agent's log group: Runtime did that on first
invocation. It creates no evaluation resources either, which is Module 2's job.
:::

## Verify

Check the trace **destination**, not just whether the log group exists. The
`aws/spans` group can exist while traces still go to the X-Ray backend:

```bash
aws xray get-trace-segment-destination --region us-east-1
```

Expected: `"Destination": "CloudWatchLogs"` with `"Status": "ACTIVE"`.

A fresh flip takes **6 to 10 minutes** to reach `ACTIVE`, so `PENDING` here is normal.
**Do not sit and wait for it.** Path A.4 opens with a check that confirms the pipeline is
genuinely accepting spans, which is a stronger test than this status, and it tells
you what to do meanwhile.

:::alert{type="warning" header="If the destination still says XRay, or the stack failed on TxnSearchEnable"}
The Lambda's log group (`/aws/lambda/edd-observability-txn-search`) names the
cause. Enabling Transaction Search makes X-Ray call several APIs on your behalf,
and each needs its own permission:

| Error in the Lambda log | Missing piece |
|---|---|
| `not authorized to perform: application-signals:StartDiscovery` | The caller's permissions. `UpdateTraceSegmentDestination` calls Application Signals' `StartDiscovery` for you, so the caller needs that plus `iam:CreateServiceLinkedRole`. |
| `not authorized to perform: logs:PutRetentionPolicy` | The same call sets retention on `aws/spans`. |
| `XRay does not have permission to call PutLogEvents on the aws/spans Log Group` | The CloudWatch Logs resource policy letting `xray.amazonaws.com` write to `log-group:aws/spans:*` (note: no leading slash). The template's Lambda creates it; a conflicting pre-existing policy can block it. |
| `Updates are not allowed while the current status is PENDING` | Nothing is wrong, a change is already in flight. Wait for the status to leave `PENDING`, then retry. |

The workshop template grants all of these, so a fresh account should complete on
the first attempt in under 10 seconds.
:::

## Where this leaves you

The account can now keep spans. Nothing has been recorded yet, because telemetry
only captures invocations that happen after the pipeline goes live. That is Path
A.4, and it starts by confirming exactly that.
