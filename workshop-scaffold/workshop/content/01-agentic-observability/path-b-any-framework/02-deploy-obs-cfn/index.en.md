---
title: "Path B.2 Deploy observability infrastructure"
weight: 20
---

Your adapter needs somewhere to send spans. This step deploys that, one small CloudFormation template already staged in your workspace.

## Step 1: Deploy the stack

:::code{language=bash showCopyAction=true showLineNumbers=false}
source /workshop/edd-workshop/config.env
cd /workshop/edd-workshop

aws cloudformation deploy \
  --stack-name edd-observability \
  --template-file cfn/agentcore-observability.yaml \
  --parameter-overrides ServiceName=${SERVICE_NAME} \
  --capabilities CAPABILITY_IAM \
  --no-fail-on-empty-changeset \
  --region us-east-1
:::

Wait for `Successfully created/updated stack` (2 to 4 minutes).

## Step 2: Verify all three pieces

**Predict first:** on a fresh account, which of these already existed before this deploy, the `aws/spans` log group, the agent's log group, or neither? (Module 0's empty dashboard is the clue.)

:::code{language=bash showCopyAction=true showLineNumbers=false}
# 1. Where do traces go? (Transaction Search on = CloudWatchLogs)
aws xray get-trace-segment-destination --region us-east-1

# 2. The agent's log group.
aws logs describe-log-groups \
  --log-group-name-prefix /aws/bedrock-agentcore/runtimes/${SERVICE_NAME} \
  --region us-east-1 --query 'logGroups[].logGroupName' --output text

# 3. The spans log group.
aws logs describe-log-groups --log-group-name-prefix aws/spans \
  --region us-east-1 --query 'logGroups[].logGroupName' --output text
:::

Expected:

1. `"Destination": "CloudWatchLogs"`. `"Status"` starts at `PENDING`, see Step 3.
2. `/aws/bedrock-agentcore/runtimes/travel-agent-edd-workshop`
3. `aws/spans`

**Answer:** neither existed. A fresh account starts with `Destination: XRay` and no log groups, which is exactly why Module 0's dashboard was empty. Nothing observes an agent by default; every piece of this pipeline exists because something deployed it.

## Step 3: Wait for Transaction Search to go ACTIVE

:::alert{type="warning" header="Do not run the agent until this prints ACTIVE"}
X-Ray rejects OTLP spans with `400 Bad Request` while the destination is still `PENDING`, so Path B.4 fails with an export error even when your adapter is perfect.

```bash
aws xray get-trace-segment-destination --region us-east-1 --query 'Status' --output text
```

Expect **6 to 10 minutes** from stack completion to `ACTIVE`. Build the adapter (Path B.3) while it settles: B.4 opens with a check that confirms the pipeline is accepting spans before you rely on it.
:::

## What the stack actually created

:::alert{type="info" header="Plumbing: the three pieces and why each is needed"}
1. **Transaction Search wiring**: flips X-Ray's trace destination to CloudWatch Logs so OTLP spans land in `aws/spans`, and grants X-Ray the resource policy it needs to write there.
2. **The agent's log group** `/aws/bedrock-agentcore/runtimes/<service.name>`, which the adapter names in its `aws.log.group.names` resource attribute.
3. **Field-index policies** on both log groups, so Module 2's evaluator can resolve sessions by `service.name` and `session.id`.

`SERVICE_NAME` (default `travel-agent-edd-workshop`) is the join key for the whole pipeline: the log group name, the adapter's OTEL `service.name`, and Module 2's evaluation config all key on it.

This step is identical for every framework. Only the adapter in Path B.3 is framework-flavored.
:::

:::alert{type="info" header="Plumbing: Transaction Search is account-level and one-time"}
The destination flip and the `aws/spans` group are per-account, per-region. If you already enabled Transaction Search (for example by doing Path A first), the template detects it and skips that piece. The per-agent pieces are still created for your `ServiceName`.
:::

:::alert{type="warning" header="If the destination stays at XRay, or the stack fails on TxnSearchEnable"}
Enabling Transaction Search needs three things. The Lambda's log group `/aws/lambda/edd-observability-txn-search` tells you which is missing:

| Error in the Lambda log | Missing piece |
|---|---|
| `not authorized to perform: application-signals:StartDiscovery` | Caller IAM permissions. `UpdateTraceSegmentDestination` calls Application Signals' `StartDiscovery` on your behalf, so the caller needs that action plus `iam:CreateServiceLinkedRole` for `AWSServiceRoleForCloudWatchApplicationSignals`. The most common hard failure. |
| `XRay does not have permission to call PutLogEvents on the aws/spans Log Group` | The CloudWatch Logs resource policy granting `xray.amazonaws.com` → `logs:PutLogEvents` on `log-group:aws/spans:*` (note: `aws/spans`, no leading slash). The template's Lambda creates it; a conflicting pre-existing policy can block it. Check `aws logs describe-resource-policies --region us-east-1`. |
| `Updates are not allowed while the current status is PENDING` | Nothing is wrong, a change is already in flight. Wait for the status to leave `PENDING`, then retry. |

With all three satisfied the custom resource completes in under 10 seconds.
:::

**Next: [Path B.3 Build the adapter](../03-build-adapter/).**
