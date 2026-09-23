---
title: "2.2 Deploy the evaluator"
weight: 20
---

:::alert{type="info" header="This is a separate stack from Module 1"}
Module 1 enabled Transaction Search and got your agent emitting telemetry. This module deploys a **new** stack `edd-eval-and-obs` that adds evaluation on top: it **ensures** the agent runtime log group `/aws/bedrock-agentcore/runtimes/<SERVICE_NAME>` exists (creating it if missing, adopting it if Module 1 or your agent already created it, with the session index policy the evaluator needs), plus the evaluator and the Online Evaluation Config.
:::

:::alert{type="info" header="Why the template doesn't declare the log group as a plain resource"}
Your Module 1 path already created `/aws/bedrock-agentcore/runtimes/<SERVICE_NAME>` (Path B's `edd-observability` stack creates it; Path A's Runtime creates it on first invoke). If this template declared it as a regular `AWS::Logs::LogGroup`, CloudFormation's pre-deploy validation would reject the changeset with `AWS::EarlyValidation::ResourceExistenceCheck`, because you can't declaratively create a named resource that already exists. Instead the template uses a small custom resource that **creates-or-adopts** the log group idempotently. This is a pattern worth stealing for any stack that layers onto infrastructure another stack may own.
:::

## What you'll do

Deploy `cfn/agentcore-eval-and-obs.yaml` which creates:

- An **evaluator** (Builtin.Helpfulness by default)
- An **Online Evaluation Config** that watches your agent's log group
- An **eval-execution IAM role** that grants the evaluator permission to read logs and invoke the judge model

## Deploy the stack

**If you took Path B** (any framework, this workshop's pi-mono):

```bash
source /workshop/edd-workshop/config.env
cd /workshop/edd-workshop

aws cloudformation deploy \
  --stack-name edd-eval-and-obs \
  --template-file cfn/agentcore-eval-and-obs.yaml \
  --parameter-overrides \
    ServiceName=${SERVICE_NAME} \
    EvaluatorMode=Builtin \
    ArtifactsBucket=${ARTIFACTS_BUCKET} \
    ArtifactsPrefix=${ARTIFACTS_PREFIX} \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset
```

**If you took Path A** (Strands on AgentCore Runtime), pass **both** names from Path A.2, because the log group and the emitted `service.name` differ:

```bash
source /workshop/edd-workshop/config.env
cd /workshop/edd-workshop

# Both were captured in Path A.2. Re-derive them if this is a new shell.
echo "log suffix   = $RUNTIME_LOG_SUFFIX"     # e.g. myAgent-ABC123-DEFAULT
echo "service.name = $RUNTIME_SERVICE_NAME"   # e.g. myAgent.DEFAULT

aws cloudformation deploy \
  --stack-name edd-eval-and-obs \
  --template-file cfn/agentcore-eval-and-obs.yaml \
  --parameter-overrides \
    ServiceName=${RUNTIME_LOG_SUFFIX} \
    EmittedServiceName=${RUNTIME_SERVICE_NAME} \
    EvaluatorMode=Builtin \
    ArtifactsBucket=${ARTIFACTS_BUCKET} \
    ArtifactsPrefix=${ARTIFACTS_PREFIX} \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset
```

Wait for `CREATE_COMPLETE`. On a fresh account this takes **4 to 8 minutes**: the stack
builds the provisioner Lambda and the eval-execution role, then calls
`CreateOnlineEvaluationConfig` and waits for it to settle.

:::alert{type="warning" header="Path A: two different names, or nothing gets scored"}
`ServiceName` builds the log group the evaluator reads. `EmittedServiceName` is the `service.name` filter applied to records inside it. On AgentCore Runtime these are **not** the same string: the log group keeps the runtime id (`myAgent-ABC123-DEFAULT`) while records carry the dot-joined `myAgent.DEFAULT`.

Pass only the log suffix and the filter matches zero records: the config goes `ACTIVE`, no error appears, and no session is ever scored. Leaving `EmittedServiceName` blank is correct for Path B only, where the two values are identical.
:::

:::alert{type="warning" header="Deploying this stack for the OTHER path later? Pass EmittedServiceName explicitly"}
`aws cloudformation deploy` **keeps every parameter you do not pass**. So if this stack was already
deployed for Path A and you now deploy it for Path B with only `ServiceName=${SERVICE_NAME}`, the
stack silently retains Path A's `EmittedServiceName`. The template computes the filter as
"`EmittedServiceName` if set, else `ServiceName`", so you end up with a config that reads the **Path B
log group** while filtering for the **Path A service name**: `ACTIVE`, no error, zero sessions scored.

Measured on an account that did Path A first. After the Path B deploy above, without
`EmittedServiceName`:

```
logGroupNames: ["/aws/bedrock-agentcore/runtimes/travel-agent-edd-workshop"]   <- Path B
serviceNames:  ["travelAgentStrands_travelAgent.DEFAULT"]                      <- still Path A
```

Passing it explicitly fixes it, and is harmless when the values are already equal:

```bash
aws cloudformation deploy \
  --stack-name edd-eval-and-obs \
  --template-file cfn/agentcore-eval-and-obs.yaml \
  --parameter-overrides \
    ServiceName=${SERVICE_NAME} \
    EmittedServiceName=${SERVICE_NAME} \
    EvaluatorMode=Builtin \
    ArtifactsBucket=${ARTIFACTS_BUCKET} \
    ArtifactsPrefix=${ARTIFACTS_PREFIX} \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset
```

Two follow-on effects worth knowing. The corrected deploy creates a **new** config (its name is derived
from the service name) and **leaves the old one ACTIVE**, so delete the stale one or it keeps invoking a
judge. And with two configs present, `onlineEvaluationConfigs[0]` can return either, which is the same
trap 4.2 step 1 warns about for results log groups: resolve by name, not by index.
:::

:::alert{type="info" header="Why CAPABILITY_NAMED_IAM (not just CAPABILITY_IAM)?"}
The stack creates the eval-execution role with an **explicit name**
(`${ProjectName}-eval-exec`) so the Online Evaluation Config can reference a stable ARN.
Any template with a named IAM resource requires `CAPABILITY_NAMED_IAM`. With only
`CAPABILITY_IAM` the deploy fails immediately with
`InsufficientCapabilitiesException: Requires capabilities : [CAPABILITY_NAMED_IAM]`.
(`CAPABILITY_NAMED_IAM` is a superset, so it also covers the unnamed roles in the stack.)
:::

:::alert{type="warning" header="Deploy rolled back with a ROLLBACK_COMPLETE / IAM role name conflict?"}
The stack's `ProjectName` parameter defaults to `edd-workshop` and is used to build that
**fixed** IAM role name (`${ProjectName}-eval-exec`). In a Workshop-Studio-provisioned
sandbox (one fresh account per event) this never collides. But if you're re-running this
module in a shared or reused AWS account (practicing locally, or re-deploying after a
prior attempt), a second deploy with the default `ProjectName` collides on that role name
and rolls back.

Fix: pass a unique `ProjectName` override:

```bash
aws cloudformation deploy \
  --stack-name edd-eval-and-obs \
  --template-file cfn/agentcore-eval-and-obs.yaml \
  --parameter-overrides \
    ServiceName=${SERVICE_NAME} \
    EvaluatorMode=Builtin \
    ArtifactsBucket=${ARTIFACTS_BUCKET} \
    ArtifactsPrefix=${ARTIFACTS_PREFIX} \
    ProjectName=edd-workshop-$(date +%s | tail -c 6) \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset
```
:::

## Verify the config is active

Once the stack finishes, confirm the Online Evaluation Config was created and is active:

```bash
aws bedrock-agentcore-control list-online-evaluation-configs \
  --region us-east-1 \
  --query 'onlineEvaluationConfigs[?contains(onlineEvaluationConfigName, `edd_workshop`)].{name:onlineEvaluationConfigName, status:status}' \
  --output table
```

You should see a table with one row showing `status: ACTIVE`.

:::alert{type="warning" header="Need a recent AWS CLI v2 for the evaluator commands"}
The `bedrock-agentcore-control` evaluator / online-evaluation subcommands (`list-online-evaluation-configs`, `list-evaluators`, `create-evaluator`, …) require a recent **AWS CLI v2**. On an older CLI the command above fails with:

```
aws: error: argument operation: Invalid choice, valid choices are: ...
```

The Workshop Studio Code Editor installs the latest CLI, so this should already work. If you see the error, check and upgrade (see Module 00's CLI-upgrade note for the macOS vs.
Linux install commands):

```bash
aws --version                       # upgrade if a subcommand reports Invalid choice
```

Upgrading is the only option here: the Code Editor ships no `boto3` and no `pip` to install it, so there is no Python fallback.
:::

:::alert{type="warning" header="Which name goes in which parameter"}
The evaluator reads the log group `/aws/bedrock-agentcore/runtimes/<ServiceName>`, then filters
the records inside it by `service.name`. Two parameters, two different jobs:

| Module 1 path | `ServiceName` builds the log group | `EmittedServiceName` filters the records |
|---|---|---|
| **Path B** (any framework, this workshop's pi-mono) | `travel-agent-edd-workshop`, the `config.env` default | leave it out: on Path B the two values are identical |
| **Path A** (Strands on AgentCore Runtime) | `$RUNTIME_LOG_SUFFIX`, hyphen-joined, keeps the runtime id | `$RUNTIME_SERVICE_NAME`, dot-joined, drops it |

If you are unsure, read the name the Runtime actually created:

```bash
aws logs describe-log-groups \
  --log-group-name-prefix /aws/bedrock-agentcore/runtimes/ \
  --query 'logGroups[*].logGroupName' --output table
```

On Path A that prints one row, for example
`/aws/bedrock-agentcore/runtimes/travelAgentStrands_travelAgent-IDyHBY845c-DEFAULT`. Everything
after `runtimes/` is your `ServiceName`.
:::

## What the stack created

The stack deployed three resources:

1. **Evaluator**: registered as `Builtin.Helpfulness` (pre-existing AWS-managed evaluator; the stack references it).
2. **Online Evaluation Config**: its name starts with `edd_workshop_`, followed by your service name. It watches your agent's log group and invokes the evaluator for every completed session.

   Match on that **prefix**, not on a suffix. Config names are capped at 48 characters
   (`^[a-zA-Z][a-zA-Z0-9_]{0,47}$`), so with a Path A service name the provisioner
   truncates and you get something like
   `edd_workshop_travelAgentStrands_travelAgent_DEFA` with the trailing
   `_helpfulness` cut off entirely.
3. **Eval Execution Role**: IAM role that the evaluation service assumes to read log events and write scores.

The evaluator is now live. Any new sessions that appear in your agent's log group will be picked up after the session-idle timeout and scored automatically.
