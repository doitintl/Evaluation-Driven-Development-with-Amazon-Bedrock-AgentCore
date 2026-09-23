---
title: "0. Set Up & Run the Travel Agent"
weight: 10
---

This module verifies your stack is alive and traces are flowing into CloudWatch.

**Your checklist for this module:**

1. Sign in to the AWS console through Workshop Studio.
2. Grab the Code Editor URL.
3. Run the agent and confirm it answers.
4. Verify AWS credentials and the CLI version.
5. Run a constraint-rich prompt and read the trajectory.
6. Confirm `config.env`, then look at the empty GenAI Observability dashboard.

:::alert{type="info" header="Background: audience, prerequisites, and costs (optional reading)"}
For the full **objectives, learning outcomes, target audience, and prerequisites**, see the [workshop overview](../). In short:

- **Who it's for:** developers and DevOps engineers building or operating LLM agents who want measurable quality, not vibes.
- **You'll learn to:** wire agent observability (Module 1), score every session with an automated judge (Module 2), catch trajectory regressions before deploy (Module 3), and pull production patterns back into your test suite (Module 4).
- **Prerequisites:** basic AWS and command-line familiarity, plus a TypeScript/Python reading level. No prior AgentCore experience needed.

**Costs.** In an AWS-hosted event everything runs in a Workshop Studio sandbox account provisioned for you at no cost, and it is torn down automatically when the event ends. In your own account this workshop deploys billable resources (EC2 Code Editor, Lambda, CloudWatch logs, AgentCore evaluators, Bedrock invocations) costing a few US dollars end-to-end; delete the root CloudFormation stack when you finish (see the [Cleanup section](../summary/)).
:::

## Step 1: Sign in to the AWS console

Several steps in this workshop open the AWS console. Those links only work once you are signed in **as the workshop's participant role**, so do this first.

1. Log out of any AWS account you are already signed in to (your own, or your employer's). Otherwise the console links land you in the wrong account.
2. In the Workshop Studio **left navigation**, expand **AWS account access**.
3. Click **Open AWS console (us-east-1)**. It opens a new tab already signed in.

Confirm the top-right of that new tab shows **`WSParticipantRole/Participant`** and your region is **N. Virginia (us-east-1)**. Keep this tab open for the rest of the workshop.

:::alert{type="warning" header="Skipping this step breaks every console link later"}
Console links in this workshop, such as the GenAI Observability dashboard, assume this session exists. If a link bounces you to a sign-in page or shows the wrong account, come back here and open the console through Workshop Studio again.
:::

## Step 2: Grab the Code Editor URL

Open the **Event dashboard** from the Workshop Studio left navigation. It surfaces the stack outputs directly, so you can copy these without opening CloudFormation:

| Output | What it is |
|---|---|
| `CodeEditorUrl` | VS Code in your browser |
| `ServiceName` | The default OTEL `service.name` used by Path B (`travel-agent-edd-workshop`) |

All remaining interaction happens through the Code Editor terminal.

:::alert{type="info" header="Why the eval infrastructure is not pre-deployed"}
Unlike many AWS workshops, this one does NOT pre-deploy the AgentCore eval and observability infrastructure. **You** deploy the observability stack in Module 1 and the evaluator stack in Module 2. That is deliberate: you would never let a vendor pre-deploy your eval pipeline in production, so building it yourself is the point. The pre-deployed bootstrap is only a VPC and the Code Editor.
:::

## Step 3: Open the Code Editor and run the agent

Click `CodeEditorUrl`. You land in a browser-based VS Code with the workshop repo cloned at `/workshop/edd-workshop`.

On first open it may ask **"Do you trust the authors of the files in this folder?"**.
Click **"Yes, I trust the authors"**: in restricted mode the terminal and the extensions
this workshop relies on stay disabled.

Open a terminal (`Terminal → New Terminal`) and confirm the CloudFormation templates you deploy later are staged:

:::code{language=bash showCopyAction=true showLineNumbers=false}
ls /workshop/edd-workshop/cfn/
:::

You should see `agentcore-observability.yaml` (Module 1) and `agentcore-eval-and-obs.yaml` (Module 2). They were staged at provision time, so the later `aws cloudformation deploy --template-file cfn/...` commands work with no download step.

Now source the pre-baked defaults and run the agent:

:::code{language=bash showCopyAction=true showLineNumbers=false}
source /workshop/edd-workshop/config.env
cd /workshop/edd-workshop/travel-agent
npx tsx src/main.ts "What's at the Grand Museum?"
:::

**Where this is running matters later.** That command started the agent as an
ordinary process on the Code Editor EC2 instance, exactly as if you had run it on
your laptop. It works, and **nothing outside that process can see what it did**:
no trace, no record, nothing to score. Module 1 is about fixing that.

Expected output (abbreviated; your wording will vary because the agent is non-deterministic):

```
Here's what I found about the **Grand Museum of Luminara**:

- **Category:** History
- A sprawling museum housing centuries of Luminaran history, from
  ancient artifacts to modern art installations.
- **Hours:** 09:00 – 18:00
- **Closed:** Mondays
- **Suggested visit:** ~2 hours
- **Ticket Price:** $25

It sounds like a great stop for history and art lovers! Would you like
to include it in a trip itinerary?
```

:::alert{type="info" header="What that output tells you (optional reading)"}
The Coordinator invoked the `query_sites` tool, the tool returned the Grand Museum's record from the inline mock data, and the Coordinator synthesized a friendly answer. That confirms Node, the Bedrock client, and the agent code all work. The exact wording does not matter; the invariants are the right hours, the right closure day, and the right price, because those are the values the eval scores against later.

If you see `Cannot find module 'tsx'`, run `npm install` once. Dependencies were installed at provision time, so this is rare.
:::

## Step 4: Verify AWS credentials and CLI version

Run both checks:

:::code{language=bash showCopyAction=true showLineNumbers=false}
aws sts get-caller-identity --region us-east-1
aws --version
:::

Expected: an ARN ending in `:assumed-role/main-stack-CodeEditor-...-EditorRole-.../i-<instance-id>`, and a recent AWS CLI v2.

**Do not** export `AWS_PROFILE` or `AWS_ACCESS_KEY_ID`. Workshop Studio supplies credentials through the default chain, and overriding them breaks every later step.

:::alert{type="warning" header="Stop here if you see Unable to locate credentials"}
Do not continue: every later step needs these credentials. Ask a facilitator. See also this module's troubleshooting section on stray `AWS_` environment variables.
:::

:::alert{type="info" header="Two roles, two jobs (optional reading)"}
The Code Editor EC2 uses the scoped `EditorRole` instance profile for everything you run in the terminal: Bedrock invoke, AgentCore eval management, log read/write, and CFN deploy. `WSParticipantRole` is the separate console-only role from Step 1, carrying `ReadOnlyAccess` plus a small write allowlist for the workshop's own resources.
:::

:::alert{type="info" header="If a later step fails with `argument operation: Invalid choice`"}
Your AWS CLI is too old for the AgentCore `bedrock-agentcore-control` subcommands. The Code Editor installs a current CLI at provision time, so this is rare. Upgrade in place:

```bash
curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
(cd /tmp && unzip -q awscliv2.zip && sudo ./aws/install --update)
hash -r && aws --version
```

Running locally on macOS instead? The Linux installer downloads but fails with `cannot execute binary file`, so use the macOS package:

```bash
curl -fsSL "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o /tmp/AWSCLIV2.pkg
sudo installer -pkg /tmp/AWSCLIV2.pkg -target /
hash -r && aws --version
```
:::

## Step 5: Run the agent and read the trajectory

Send a constraint-rich prompt to the Coordinator:

:::code{language=bash showCopyAction=true showLineNumbers=false}
npx tsx src/main.ts "Plan a 2-day Luminara trip focused on history, arriving Monday."
:::

After ~30 seconds the Coordinator returns a 2-day itinerary.

**The one thing to check:** the **Grand Museum** lands on **Day 2 (Tuesday)**, not
Day 1 (Monday), because it closes on Mondays. The summary usually spells the
reasoning out, for example "Grand Museum moved to Tuesday (closed Monday)".

Behind that answer the Coordinator called three tools in order: `query_sites` to
look up history attractions, `plan_route` to build a schedule that respects
closures, then `suggest_dining` for meal stops. **You cannot see that sequence
here.** `src/main.ts` prints only the final answer, so the trajectory is something
you are inferring from the result. Making it visible is exactly what Module 1
does, and it is why observability comes before evaluation.

:::alert{type="info" header="Why this ordering matters (optional reading)"}
The Coordinator must call `query_sites` before `plan_route` so the route planner has accurate closure data. If you see the Grand Museum scheduled on Day 1 (Monday), the trajectory broke. Module 2 shows you how to detect exactly that with eval scores, and Module 3 turns it into a repeatable test.
:::

## Step 6: Confirm `config.env` and see the empty dashboard

Module 1 and Module 2 deploys rely on `ARTIFACTS_BUCKET` and `ARTIFACTS_PREFIX`, so confirm all five values are populated:

:::code{language=bash showCopyAction=true showLineNumbers=false}
source /workshop/edd-workshop/config.env
echo "AWS_REGION=$AWS_REGION"
echo "SERVICE_NAME=$SERVICE_NAME"
echo "ARTIFACTS_BUCKET=$ARTIFACTS_BUCKET"
echo "ARTIFACTS_PREFIX=$ARTIFACTS_PREFIX"
echo "MODEL_ID=$MODEL_ID"
:::

`ARTIFACTS_BUCKET` is a per-event Workshop Studio bucket, named like `ws-event-<event-id>-us-east-1`, and `ARTIFACTS_PREFIX` is a build-specific path ending in `/assets/`. The exact values differ for every event, so do not compare them against anyone else's. Module 1 and Module 2 pass both through so the `eval_provisioner` Lambda can load from S3.

Now switch to the AWS console tab from Step 1 and open the dashboard you will populate in Module 1:

1. Open **CloudWatch**.
2. In the left nav, expand **GenAI Observability**.
3. Click **Bedrock AgentCore**.

Direct link: [GenAI Observability, Bedrock AgentCore](https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#gen-ai-observability/agent-core) (works only in the signed-in console tab from Step 1).

**Expected result: an empty dashboard. That is correct.** Two things confirm you are
in the right place and in the "before" state:

1. A callout reading **"AgentCore Observability requires span ingestion"**, with a
   **Configure** button. It is telling you Transaction Search is not on yet.
2. **"No data / Enable Transaction Search"** where the metrics and agent list will
   appear.

![The GenAI Observability dashboard before any agent is instrumented. Box 1: the "AgentCore Observability requires span ingestion" callout, which says Transaction Search is not enabled yet. Box 2: "No data, Enable Transaction Search" in place of the OTEL metrics](/static/images/module-1/00-genai-obs-before.png)

You will turn Transaction Search on in Module 1 and come back to watch this fill in.

:::alert{type="info" header="Plumbing: do not click Configure"}
That button would enable Transaction Search from the console. Leave it alone.
Module 1 enables it through a CloudFormation template instead, so you finish with
an artifact you can take back to your own account, and so the workshop's later
steps match what you deployed.
:::

:::alert{type="info" header="Looking under Application Signals? Wrong place"}
**GenAI Observability** is its own top-level item in the CloudWatch left nav. **Application Signals (APM)** is a separate item directly below it and does not contain the agent dashboard.
:::

## What just happened

You ran the Coordinator with no observability instrumentation: answers come back, but nothing is traced. Module 1 wires that up. Pick your path based on one question, *does your agent use the Strands Agents SDK?*

- **[Path A, Strands on AgentCore Runtime](../01-agentic-observability/path-a-strands/)**: for Strands SDK agents. Deploy to AgentCore Runtime and the managed sidecar emits telemetry for you. ~20 min.
- **[Path B, any other framework](../01-agentic-observability/path-b-any-framework/)**: for anything else (LangGraph, CrewAI, custom, or this workshop's **pi-mono**). Add a small OpenInference adapter mapping lifecycle events to OpenTelemetry spans. ~45 min.

Both converge on the same evaluation-ready telemetry, so Modules 2 through 4 work identically either way.

## Troubleshooting

:::alert{type="warning" header="`aws sts get-caller-identity` fails or returns the wrong role"}
Check that no `AWS_PROFILE`, `AWS_ACCESS_KEY_ID`, or `AWS_SESSION_TOKEN` env vars are set in the terminal: `env | grep AWS_`. If any are set, run `unset AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN` and retry. Workshop Studio's Code Editor relies on the EC2 instance metadata service.
:::

:::alert{type="warning" header="`npx tsx src/main.ts` errors with an aws-marketplace:Subscribe AccessDeniedException"}
Fresh AWS sandbox accounts haven't subscribed to the Bedrock Sonnet 4.6 model in AWS Marketplace yet. The first call from your EC2's IAM role triggers the auto-subscribe path, which takes ~60-90s to propagate. Workshop Studio's account often hits this on the very first invocation.

Wait 90 seconds, then re-run the same command. The second attempt usually succeeds. If it still fails after 3 attempts, ask a facilitator to verify Bedrock model access for `us.anthropic.claude-sonnet-4-6` in the Bedrock console.
:::

:::alert{type="warning" header="`npm install` fails with permission errors"}
The Code Editor's home directory is owned by the `ec2-user` account. If you opened the terminal as `root` (rare in Workshop Studio), switch back: `su - ec2-user`. If `npm install` reports a network error, retry once. NAT Gateway egress can take a moment to settle on a fresh stack.
:::

:::alert{type="warning" header="No traces in GenAI Observability"}
That's expected right now. The agent emits responses but no telemetry until you wire it up in Module 1 (Path A deploys to AgentCore Runtime; Path B adds the OpenInference adapter). Use the terminal output to verify the trajectory in the meantime.
:::

When everything is green, continue to **[Module 1: Agentic Observability](../01-agentic-observability/)** and pick the path that matches your stack.
