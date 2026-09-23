---
title: "2.6 (Optional) Custom evaluator"
weight: 55
---

:::alert{type="info" header="Optional step"}
This step is optional. If you are short on time, skip ahead to the summary. You can always return to it later.
:::

## Why go custom?

`Builtin.Helpfulness` is a generic quality score. It cannot tell you whether the agent respected domain-specific constraints: for example, that the Grand Museum is closed on Mondays, or that `query_sites` must be called before `plan_route`.

A **custom evaluator** lets you define exactly what "good" means for your use case using a rubric and a 1-5 scale.

## Redeploy with Custom mode

Update the stack to use a custom evaluator with a domain-specific rubric. **Pass the same
name parameters you used in step 2.2**, changing only `EvaluatorMode`.

**If you took Path B** (any framework, this workshop's pi-mono):

```bash
source /workshop/edd-workshop/config.env
cd /workshop/edd-workshop

aws cloudformation deploy \
  --stack-name edd-eval-and-obs \
  --template-file cfn/agentcore-eval-and-obs.yaml \
  --parameter-overrides \
    ServiceName=${SERVICE_NAME} \
    EvaluatorMode=Custom \
    ArtifactsBucket=${ARTIFACTS_BUCKET} \
    ArtifactsPrefix=${ARTIFACTS_PREFIX} \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset
```

**If you took Path A** (Strands on AgentCore Runtime), pass **both** names, exactly as in
step 2.2:

```bash
source /workshop/edd-workshop/config.env
cd /workshop/edd-workshop

echo "log suffix   = $RUNTIME_LOG_SUFFIX"     # e.g. myAgent-ABC123-DEFAULT
echo "service.name = $RUNTIME_SERVICE_NAME"   # e.g. myAgent.DEFAULT

aws cloudformation deploy \
  --stack-name edd-eval-and-obs \
  --template-file cfn/agentcore-eval-and-obs.yaml \
  --parameter-overrides \
    ServiceName=${RUNTIME_LOG_SUFFIX} \
    EmittedServiceName=${RUNTIME_SERVICE_NAME} \
    EvaluatorMode=Custom \
    ArtifactsBucket=${ARTIFACTS_BUCKET} \
    ArtifactsPrefix=${ARTIFACTS_PREFIX} \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset
```

:::alert{type="warning" header="Path A: omitting EmittedServiceName silently stops all scoring"}
`aws cloudformation deploy` keeps a parameter's **previous** value only if you pass
`--parameter-overrides ... EmittedServiceName=` explicitly or omit the parameter from a
template that defaults it. If you drop it here and pass only
`ServiceName=${SERVICE_NAME}`, the regenerated config ends up watching the wrong log
group while filtering the wrong `service.name`.

The failure is invisible: the stack reports `UPDATE_COMPLETE`, the config reports
`ACTIVE`, and **zero sessions are ever scored**. Measured on a live account: the
mismatched config logged 0 events while the correctly-parameterised one logged 2. If
`read-eval-scores.sh` returns nothing after 25 minutes, check this first.
:::

Wait for `UPDATE_COMPLETE`. Expect **4 to 8 minutes**: the update deletes and recreates
the Online Evaluation Config.

:::alert{type="info" header="Verify, don't just trust UPDATE_COMPLETE"}
This is an in-place update of the same stack, switching `EvaluatorMode` on an existing
deployment. CloudFormation reporting `UPDATE_COMPLETE` confirms the stack update
succeeded, but doesn't by itself prove the Online Evaluation Config still has your
evaluator attached. First confirm the config exists and is active:

```bash
aws bedrock-agentcore-control list-online-evaluation-configs \
  --region us-east-1 \
  --query 'onlineEvaluationConfigs[?contains(onlineEvaluationConfigName, `edd_workshop`)].{name:onlineEvaluationConfigName, status:status}' \
  --output table
```

`ACTIVE` is necessary but not sufficient: a config with **no** evaluator attached also reports
`ACTIVE` and silently scores nothing. So read the attachment itself:

```bash
CFG=$(aws bedrock-agentcore-control list-online-evaluation-configs \
  --region us-east-1 \
  --query 'onlineEvaluationConfigs[0].onlineEvaluationConfigId' --output text)

aws bedrock-agentcore-control get-online-evaluation-config \
  --online-evaluation-config-id "$CFG" --region us-east-1 \
  --query '[status,evaluators]' --output json
```

Expected, with your own suffix:

```json
[
  "ACTIVE",
  [
    {
      "evaluatorId": "edd_workshop_travel_quality-XXXXXXXXXX"
    }
  ]
]
```

Two things to read: the list is **not empty**, and `Builtin.Helpfulness` is **gone**. The
switch replaces the evaluator rather than adding to it. (The field is `evaluators`; there is
no `evaluatorConfigs`.)

If the config is missing, the status isn't `ACTIVE`, or `evaluators` is empty, the safest
recovery is to delete the stack and redeploy fresh directly in the target mode, rather than
repeatedly retrying an in-place switch:

```bash
aws cloudformation delete-stack --stack-name edd-eval-and-obs
aws cloudformation wait stack-delete-complete --stack-name edd-eval-and-obs
# then re-run the deploy command above
```
:::

## What changed

The stack now creates a **custom evaluator** that scores sessions on a 1-5 scale using a travel-domain rubric. The rubric instructs the judge model to check:

- Did the agent provide accurate information about attractions and opening hours?
- Did it respect known constraints (e.g., closures, booking requirements)?
- Was the response well-structured and actionable?

The Online Evaluation Config is updated to use this custom evaluator instead of `Builtin.Helpfulness`.

## Generate new traffic

Invoke the agent with a query that tests domain awareness, using the same method as in step 2.3:

```bash
# Path B (this workshop's pi-mono OpenInference adapter)
cd /workshop/edd-workshop/openinference-aws-adapter
USER_QUERY="Plan a Monday visit to the Grand Museum in Luminara" npm start
USER_QUERY="What is open on Sunday morning in Luminara?"          npm start
```

:::alert{type="info" header="Path A"}
If you took Path A (Strands on AgentCore Runtime), generate traffic with `agentcore invoke "<query>"` from `travel-agent-strands/` instead.
:::

## Verify custom scores

Allow up to 20-25 minutes (see the timing note in step 2.1), then check the evaluation log group:

```bash
cd /workshop/edd-workshop
./scripts/read-eval-scores.sh
```

Use `--max-items` here, not `--limit`, see the warning in step 2.3 for why.

## Expected output

Custom evaluator scores use the 1-5 scale from your rubric instead of 0.0-1.0, and carry
a rubric-defined label:

```
Reading /aws/bedrock-agentcore/evaluations/results/edd_workshop_..._DEFA-h8MFHfGuoF

  edd_workshop_travel_quality (2 score(s))
    session b0be1052-5454-4edc-adc   score=4.0   Very Good
      Evaluating the agent's response across three dimensions:
      1. FACTUAL ACCURACY: The response presents a well-organized table of attractions...
    session 324a4efc-bfb9-4238-ad3   score=4.0   Very Good
      ...

  2 score(s) across 1 evaluator(s)
```

The underlying log record carries the same values as OTEL attributes:

```json
{
  "gen_ai.evaluation.name": "edd_workshop_travel_quality",
  "gen_ai.evaluation.score.value": 4,
  "gen_ai.evaluation.score.label": "Very Good",
  "gen_ai.evaluation.explanation": "Let me evaluate this response across the three dimensions: 1. FACTUAL ACCURACY: ...",
  "session.id": "3e869096-2f71-4c5b-913c-0edef93c1c3d"
}
```

Two details, both measured on a live record. The evaluator arrives under
`gen_ai.evaluation.name`, the same key `Builtin.Helpfulness` used, so a query written in step 2.3
keeps working unchanged. And the **name in the record carries no suffix**: the config references
`edd_workshop_travel_quality-XXXXXXXXXX`, with a service-generated suffix, while the score record
says plainly `edd_workshop_travel_quality`. Match on the bare name when you filter records, and on
the suffixed id when you address the evaluator through the API.

`Builtin.Helpfulness` no longer appears at all, because the config now runs your evaluator in its
place.

## Compare the two approaches

| | Builtin.Helpfulness | Custom evaluator |
|---|---|---|
| **Scale** | 0.0-1.0 (float) | 1-5 (integer) |
| **Setup** | Zero config | Rubric authoring required |
| **Domain awareness** | Generic quality | Domain-specific constraints |
| **Use case** | Broad quality smoke detector | Precision scoring for your domain |

Both approaches serve different purposes. In production, you might run **both**: Builtin for general quality monitoring and Custom for domain-specific regression detection.
