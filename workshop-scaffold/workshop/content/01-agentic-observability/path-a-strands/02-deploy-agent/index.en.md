---
title: "Path A.2 Deploy the agent to AgentCore Runtime"
weight: 20
---

**Scenario.** Module 0 ran the agent as an ordinary process on your Code Editor
EC2 instance, the same as running it on a laptop. Nothing outside that process
could see what it did. You would not run a production agent that way, so this step
moves it onto managed infrastructure: **Amazon Bedrock AgentCore Runtime**, which
also gives you telemetry you do not have to write.

:::alert{type="info" header="Learn: what Amazon Bedrock AgentCore Runtime is"}
**AgentCore** is a set of managed services for running and operating AI agents in
production. This workshop uses three of them: **Runtime** (hosts your agent),
**Observability** (collects its traces and records), and **Online Evaluation**
(scores its sessions). It has other components, Memory, Gateway, Identity, that
this workshop does not touch.

**Runtime** hosts your agent code in a managed container with its own IAM
execution role, and injects a telemetry sidecar next to it. That sidecar is why
Path A needs no instrumentation code: it emits the traces and records for you.

Path B keeps the agent running where it already runs and instruments it by hand
instead. Both reach the same evaluation pipeline. Neither is more "production"
than the other; the difference is who runs the container.

[AgentCore Runtime documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime.html)
:::

## 2.1: Inspect the AgentCore project

This path uses the **AgentCore CLI** (`@aws/agentcore`, a Node package). The
project ships an `agentcore/` directory describing what to deploy.

In the Code Editor **Explorer**, open
`travel-agent-strands/agentcore/agentcore.json`. The fields that matter:

```json
{
  "name": "travelAgentStrands",
  "managedBy": "CDK",
  "runtimes": [
    {
      "name": "travelAgent",
      "build": "CodeZip",
      "entrypoint": "runtime/main.py",
      "codeLocation": ".",
      "runtimeVersion": "PYTHON_3_12",
      "networkMode": "PUBLIC",
      "protocol": "HTTP",
      "environmentVariables": {
        "AWS_REGION": "us-east-1",
        "MODEL_ID": "us.anthropic.claude-sonnet-4-6",
        "UNIFIED_TRACES_DESTINATION_ENABLED": "false"
      }
    }
  ],
  "memories": []
}
```

Now open `travel-agent-strands/runtime/main.py`. It is short. The wrapper exposes
your Coordinator as `@app.entrypoint`, and Runtime calls it once per request.

Then set up your shell for the rest of this page:

```bash
source /workshop/edd-workshop/config.env
cd /workshop/edd-workshop/travel-agent-strands
```

:::alert{type="info" header="Plumbing: what those fields mean"}
- **`build: CodeZip`**: your Python is zipped and uploaded, with no Docker and no local build. `uv` resolves dependencies and is pre-installed on the Code Editor.
- **`entrypoint: runtime/main.py`**: wraps the Coordinator in a `BedrockAgentCoreApp`. It imports `create_coordinator_agent()` from `src/coordinator.py`, extracts `payload["prompt"]`, and runs the agent.
- **`memories: []`**: this agent is stateless per invocation, so no AgentCore Memory is created and the deploy needs no memory permissions. (The new-CLI equivalent of the old toolkit's `--disable-memory`.)
- **`UNIFIED_TRACES_DESTINATION_ENABLED: "false"`**: pins where spans are written. See the box below.
:::

:::alert{type="info" header="Learn: two possible homes for your spans, and why this workshop picks one"}
AgentCore can write an agent's spans to either of two places:

| Destination | Where spans land |
|---|---|
| Shared (what this workshop uses) | the account-wide `aws/spans` log group |
| Unified (newer default) | a `spans` stream inside the agent's own log group |

Unified storage keeps an agent's spans, prompts and logs together, which makes
per-agent IAM scoping and encryption possible. It became the default for newly
created agents in July 2026, and it takes effect only when the agent runs ADOT
0.18.0 or later.

This workshop sets the variable to `false` so **every participant gets the same
destination regardless of which ADOT version the managed sidecar happens to ship**.
Every later step, and Modules 2 through 4, read `aws/spans`, so pinning this keeps
the instructions true rather than dependent on a platform default that can change
underneath us.

In your own project, prefer leaving it unset and using the unified default: it is
the better design. Just be aware which one you are on before writing queries.
[Span destination documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html)
:::

## 2.2: Verify the AgentCore CLI

The CLI is pre-installed on the Code Editor:

```bash
agentcore --help
```

Expect a command list including `create`, `deploy`, `invoke`, `status`, and `logs`.

:::alert{type="warning" header="If you see command not found"}
Install it (Node 20+ is pre-installed):

```bash
npm install -g @aws/agentcore
```
:::

:::alert{type="info" header="Learn: what CDK is, and why the CLI uses it"}
**AWS CDK** (Cloud Development Kit) describes infrastructure in a programming
language and generates a CloudFormation template from it. The AgentCore CLI uses
CDK internally, so `agentcore deploy` is really "synthesize a CDK app, then
deploy the resulting CloudFormation stack".

You do not need to know CDK for this workshop: the CLI writes and deploys it. The
reason to know it is happening is that when something fails, the error may come
from CloudFormation rather than from the CLI, and you will find a real stack in
the CloudFormation console.

CDK requires a one-time per-account setup called bootstrapping. The Code Editor
already ran it at provision time.
[AWS CDK documentation](https://docs.aws.amazon.com/cdk/v2/guide/home.html)
:::

:::alert{type="warning" header="If deploy later says the environment is not bootstrapped"}
Run `cdk bootstrap` once, then retry the deploy.
:::

## 2.3: Point the project at this account

`agentcore deploy` needs an `aws-targets.json` naming the account + region to deploy into. Generate it for **this** workshop account (the file is account-specific, so it isn't committed):

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
cat > agentcore/aws-targets.json <<EOF
[
  { "name": "default", "account": "$ACCOUNT_ID", "region": "us-east-1" }
]
EOF
cat agentcore/aws-targets.json
```

Check the project config before deploying:

```bash
agentcore validate
```

Expected output, one word:

```
Valid
```

:::alert{type="info" header="Learn: what `validate` checks, and what invalid looks like"}
`validate` is a schema check on `agentcore.json`. It confirms the file is valid
JSON and that every field holds a value the API will accept. On success it prints
exactly `Valid`.

Invalid output names the problem. A bad enum value lists the accepted ones:

```
/workshop/edd-workshop/travel-agent-strands/agentcore/agentcore.json:
  - root: expected "PYTHON_3_10" | "PYTHON_3_11" | "PYTHON_3_12" | "PYTHON_3_13" | "PYTHON_3_14"
```

and malformed JSON is reported with a position:

```
Invalid JSON in agentcore.json: Expected property name or '}' in JSON at position 2 (line 1 column 3)
```

**Know what it does not check.** It is a check on the config file, not on your
project or your account. An `entrypoint` naming a file that does not exist still
reports `Valid`, and so do missing IAM permissions, missing model access, and an
unbootstrapped CDK environment. `Valid` means "this file is well formed", not
"this deploy will work".

Running it is optional, since `deploy` does its own checks. It is worth two
seconds because `deploy` takes a few minutes, and a typo caught here is one you
do not discover partway through a CloudFormation rollback.
:::

## 2.4: `agentcore deploy`

```bash
agentcore deploy -y
```

This:

- Packages `runtime/main.py` + `src/` as a **CodeZip** archive (using `uv` to resolve `requirements.txt`).
- Synthesizes a CDK app and deploys it as a CloudFormation stack: creating the IAM execution role, uploading the code, and provisioning the AgentCore Runtime.
- Polls until the Runtime is ready.

The CLI ticks off each step with a `✓`, then prints the stack outputs and what to do next.
Abbreviated, with your account id and runtime suffix in place of the placeholders:

```
✓ Check bootstrap status
✓ Check stack status
✓ Deploy to AWS
✓ Persist deployment state

✓ Deployed to 'default' (stack: AgentCore-travelAgentStrands-default)

Outputs:
  ApplicationAgentTravelAgentRuntimeArnOutput93A546CA: arn:aws:bedrock-agentcore:us-east-1:<account>:runtime/travelAgentStrands_travelAgent-<id>
  ApplicationAgentTravelAgentRoleArnOutputD87AEDAF: arn:aws:iam::<account>:role/AgentCore-travelAgentStra-ApplicationAgentTravelAge-<id>
  ApplicationAgentTravelAgentRuntimeIdOutput727EEFDB: travelAgentStrands_travelAgent-<id>
  StackNameOutput: AgentCore-travelAgentStrands-default
Next: agentcore invoke | agentcore status

Log: agentcore/.cli/logs/deploy/deploy-<timestamp>.log
```

Total: 2 to 5 minutes. Add `-v` for resource-level deploy events if you want to watch it build.

That `RuntimeIdOutput` value is the runtime suffix Path A.2's capture step is about to read,
so it is worth a glance now.

Every run also writes a full transcript to the `Log:` path, where each step carries a duration
and the run ends with its own `Total Duration` (1m 50s on a fresh sandbox account). The log is
more verbose than the terminal, and it is the first place to look if a deploy is slow or fails.

:::alert{type="info" header="Two things a first deploy prints that look like problems and are not"}
**1. A dependency-version notice.** The `Sync CDK dependencies` step may report:

```
Your project was created before the AgentCore CLI managed dependency versions.
We've updated agentcore/cdk/package.json so the CLI keeps these dependencies
on versions it has been tested with (patch updates still apply automatically):

  @aws/agentcore-cdk   ^0.1.0-alpha.19  → 0.1.0-alpha.45
  aws-cdk-lib          ^2.248.0         → ~2.261.0
  ...
```

The CLI is pinning the checked-in CDK app to versions it has tested. Nothing to do.

**2. An Application Signals permission warning**, at the very end, right before
`COMPLETED SUCCESSFULLY`:

```
[WARN] Transaction search setup warning: Insufficient permissions to enable
Application Signals: User: arn:aws:sts::<account>:assumed-role/...-EditorRole/...
is not authorized to perform: application-signals:StartDiscovery
```

The CLI tries to switch Transaction Search on for you, and the Code Editor's role
deliberately does not grant that. **Path A.3 enables Transaction Search properly**, via
CloudFormation and the X-Ray API, which is why this warning is safe to ignore. The deploy
itself succeeded: read the `COMPLETED SUCCESSFULLY` line below the warning.
:::

:::alert{type="warning" header="If you get a Bedrock or Marketplace AccessDeniedException"}
The account's model subscription for `us.anthropic.claude-sonnet-4-6` is still
propagating. The Code Editor pre-warms it at provision time, so this is rare. Wait
60 to 90 seconds and re-run. See Module 0's troubleshooting note.
:::

## Smoke-test the deployed agent

Your agent now runs on managed infrastructure rather than in your Code Editor. The
CLI takes the prompt directly, with no JSON envelope:

```bash
agentcore invoke "What is the Grand Museum?"
```

Expected: the same Luminara-grounded answer as Module 0, with hours, closure days,
and price. Same agent, same data, different home.

:::alert{type="warning" header="If the invoke times out"}
The Runtime took too long to cold-start. Re-run the same command.
:::

## Capture the auto-generated names

Runtime generated the names for you, so the next steps need to read them back out
of your account. One command captures both and saves them:

```bash
cd /workshop/edd-workshop
./scripts/capture-runtime-names.sh
source config.env
```

Expected output: two values, and confirmation they were written to `config.env`.

```
  RUNTIME_LOG_SUFFIX   = travelAgentStrands_travelAgent-ABC123-DEFAULT
  RUNTIME_SERVICE_NAME = travelAgentStrands_travelAgent.DEFAULT
```

Because they land in `config.env`, which every new terminal sources on login, the
rest of Path A and Module 2 pick them up automatically. You will not have to
re-run this.

:::alert{type="info" header="Learn: why Runtime produces two different names"}
Runtime uses two forms of the same identity, and they are not interchangeable:

| Value | Shape | Used by |
|---|---|---|
| `RUNTIME_LOG_SUFFIX` | keeps the runtime id, hyphen-joined | the CloudWatch log group name, so Path A.3's CFN parameter |
| `RUNTIME_SERVICE_NAME` | drops the runtime id, **dot**-joined | the `service.name` stamped inside every record, so Module 2's evaluator filter |

Pass the wrong one to Module 2 and its filter matches nothing: no session is
scored, and there is no error to tell you, just an empty results log group.

The script avoids that by reading `RUNTIME_SERVICE_NAME` out of a real log record
rather than deriving it from the log-group name, so it cannot drift from what
Runtime actually writes. Open `scripts/capture-runtime-names.sh` if you want to
see how.
:::

:::alert{type="warning" header="If the script says no log group found"}
Runtime creates the log group on the **first invocation**, so this means the smoke
test above has not run yet. Run it, then re-run the script.
:::

:::alert{type="warning" header="If the script says it found more than one log group"}
You have more than one runtime deployed in this account, and the script will not
guess. It prints the names it found; re-run it with the one you just deployed:

```bash
./scripts/capture-runtime-names.sh travelAgentStrands_travelAgent-ABC123-DEFAULT
```
:::

## What you've deployed

- A CodeZip-packaged Strands agent running in AgentCore Runtime, deployed via the AgentCore CLI (CDK under the hood).
- An auto-injected OTEL sidecar emitting traces plus the canonical `invoke_agent` log event, with `service.name = <agentName>.<endpoint>` (dot-joined, no runtime id).

Next: Path A.3: deploy the observability CFN with that service name.
