---
title: "Path A.5 Recap & what's next"
weight: 50
---

## What you built

A full trajectory waterfall for every invocation, with **zero OTEL code and zero env vars** on your part:

![Trace detail for one invocation. Box 1: the span tree, which is the agent trajectory. Box 2: service.name in the resource attributes, the join key Module 2 filters on](/static/images/module-1/1a-trace-waterfall.png)

Your agent's **Evaluations** tab is the one part still empty, reading *"No evaluation
configurations to display in the selected time range"*, because no evaluator is connected
yet. Module 2 fixes that.

| Step | What you did | Effort |
|---|---|---|
| A.2 | `agentcore deploy`, then read both service names from CloudWatch | 5 commands, one of them a 2-minute deploy |
| A.3 | Deploy `agentcore-observability.yaml` with the log-group suffix | 1 CFN deploy, 2 checks |
| A.4 | Invoke and verify | 3 invocations, 2 verify runs |

:::alert{type="success" header="The one idea to take away: observability depth caps evaluation quality"}
The data you just wired up is *exactly* what Module 2's judge reads. What you capture determines what can be scored:

| What you capture | What a judge can then assess |
|---|---|
| Input and output only | Whether the final answer looks right |
| **+ tool calls (what you have now)** | **Whether the agent used the right tools in the right order** |
| + reasoning spans | Planning quality, and whether it hallucinated |

Because you captured the tool-call trajectory, Module 2 can score not just *what* the agent said but *how* it got there: did it call `query_sites` before `plan_route`, or invent the opening hours?
:::

:::alert{type="info" header="Optional: what you traded for the simplicity"}
The managed sidecar is the path of least friction, but you commit to:

- **AgentCore Runtime as the deployment target.** You cannot run this agent on your own VMs, containers, or Kubernetes. Path B is the answer when you need that.
- **The auto-generated service names.** Hence the awkward ordering: deploy the agent first (A.2) to discover the names, then deploy observability (A.3). Some teams hard-code `service.name` in `agentcore.json` to skip discovery, which is also fine.
- **The CLI's packaging model.** This deploy used **CodeZip**: `agentcore deploy` zips
  `runtime/main.py` plus `src/`, resolves `requirements.txt` with `uv`, and uploads the
  archive. No Dockerfile, no image build, no ECR repository anywhere in the path. That is
  simpler, and it means your runtime environment is whatever the CLI's managed base
  provides rather than something you pin yourself.

Worth knowing: `agentcore deploy` is a thin wrapper over CDK, CloudFormation, and IAM. You could build what it builds by hand, but you would not want to.
:::

## Where to next

- **[Module 2](../../../02-continuous-monitoring/)**: connect an automated judge that scores every session, and watch that empty tab fill with scores.
- **Module 3**: trajectory-aware evaluation with model-swap and prompt-change experiments.
- **Module 4**: turn production traffic into dev-time test cases with a coding agent.

:::alert{type="info" header="Optional: tear down Path A when you are finished"}
Workshop Studio deletes the whole account at the end of the event, so this is only needed if you are running in your own account.

```bash
# Tear down the Runtime + IAM + CDK stack the AgentCore CLI created.
# `remove all` clears the resources from the project config, then `deploy`
# applies the removal (tears down the CloudFormation stack).
cd /workshop/edd-workshop/travel-agent-strands
agentcore remove all
agentcore deploy -y

# Tear down the observability CFN
aws cloudformation delete-stack --stack-name edd-observability
```
:::
