---
title: "Summary & next steps"
weight: 90
---

You've now built the complete EDD loop end-to-end: from raw traces to automated scoring to trajectory-aware evaluation to production-derived ground truth.

## The four questions, answered

| Module | Question | Answer |
|---|---|---|
| 1. Agentic Observability | What happened? | OTEL traces + structured log records in CloudWatch |
| 2. Continuous Monitoring | Was the agent good? | Builtin.Helpfulness scores every session automatically |
| 3. Trajectory Evaluation | What specifically broke? | Framework eval catches path regressions the content judge misses |
| 4. Ground Truth Loop | What should "good" look like? | Production data informs your test suite continuously |

## The lasting insights

1. **Observability and evaluation are separate concerns.** Traces tell you *what happened*; evaluation tells you *whether it was good*. Deploy them independently so each evolves at its own pace.

2. **Two lenses, not one.** AgentCore Online Evaluation (LLM-as-Judge, prod traffic) catches content regressions you didn't anticipate. The TS framework eval scaffold catches trajectory regressions. They fail each other's tests, you need both.

3. **Trajectory and content are independent dimensions.** A model swap can improve content quality while silently regressing trajectory adherence. Without the trajectory lens, you'd ship the regression.

4. **Ground truth drifts.** Test cases written at launch represent developer assumptions, not reality. Production patterns reveal what customers actually ask. Closing the loop (production → test cases → improvements → production) keeps your evaluation honest.

5. **The wire-up scales by codifying it.** Two Powers (skills), one for wire-up, one for the EDD development loop, turn the senior engineer's habit into how the team ships every new agent.

## What to take back to your team

- **The observability CFN** (`cfn/agentcore-observability.yaml`) and the **eval CFN** (`cfn/agentcore-eval-and-obs.yaml`) are reusable templates. Drop them into any agent project.
- **The eval scaffolding** in `travel-agent/eval/` (`cases.ts`, `judge.ts`, `trajectory.ts`, `run-experiment.ts`) is a template. Replace `cases.ts` with your domain.
- **The two Powers** in `kiro-powers/` automate wire-up and case-first development. Apply them with any coding agent.
- **The production-to-dev extraction pattern** (Module 4) works with any agent that has Online Eval scoring. Low-scoring sessions are your highest-value test case candidates.

## Cleanup

:::alert{type="success" header="In an AWS-run event you can stop reading here"}
Workshop Studio reclaims the whole account at event termination, so nothing you built
persists and nothing keeps billing. The rest of this section is for **anyone running this
workshop in their own account**, where it matters, because the root stack alone does not
remove most of what you deployed.
:::

**The root stack is not enough.** You deployed the observability and evaluation stacks
yourself, as siblings of the root stack rather than nested inside it, and page 3.4 created a
Lambda, an IAM role, and an evaluator by hand with no stack at all. Deleting only the root
stack leaves all of that running, including an **ACTIVE Online Evaluation Config that keeps
invoking a judge model** on any new traffic.

Work top-down, in this order. Everything here is in the AWS console or your own terminal with
credentials that can see the whole account.

**1. The evaluation stack** (`edd-eval-and-obs`, Module 2). Delete this **first**: it owns the
Online Evaluation Config, and the next step cannot succeed while that config is still holding
an evaluator.

**2. The trajectory evaluator from 3.4**, if you did that page. It is not in any stack:

```bash
# The config from step 1 must already be gone, or this returns
# "Cannot delete a locked evaluator" (an evaluator attached to a live config).
aws bedrock-agentcore-control delete-evaluator \
  --evaluator-id "$(cat /tmp/traj_evaluator_id.txt)" --region us-east-1

aws lambda delete-function --function-name edd-trajectory-evaluator --region us-east-1
aws iam detach-role-policy --role-name trajectory-evaluator-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam delete-role --role-name trajectory-evaluator-role
```

**Also delete 2.6's custom evaluator, if you did that page.** Deleting the stack does not take it with
it: measured on a live account, `edd_workshop_travel_quality-...` was still there after every step
above, and the clean check at the bottom of this page is what caught it. Find and delete it by name:

```bash
aws bedrock-agentcore-control list-evaluators --region us-east-1 \
  --query 'evaluators[?contains(evaluatorId, `edd_workshop_travel_quality`)].evaluatorId' --output text

aws bedrock-agentcore-control delete-evaluator \
  --evaluator-id edd_workshop_travel_quality-XXXXXXXXXX --region us-east-1
```

**3. The observability stack** (`edd-observability`, Module 1).

**4. Path A only: the AgentCore Runtime.** `agentcore deploy` created its own CloudFormation
stack (`AgentCore-<project>-default`, for example `AgentCore-travelAgentStrands-default`), and the
Runtime inside it is the one resource here that costs money while idle.

:::alert{type="warning" header="In an AWS-run event, delete it from the Code Editor terminal, not the console"}
The two roles have complementary gaps, and it is the opposite of what you would guess. Measured on a
live event account:

| | `DescribeStacks` (list) | `DeleteStack` |
|---|---|---|
| Code Editor terminal (`EditorRole`) | **denied** | **works** |
| Console (`WSParticipantRole`) | works | **denied** |

So the console shows you the stacks and then refuses with "no identity-based policy allows the
`cloudformation:DeleteStack` action", while the terminal deletes happily even though it cannot list.
From the terminal:

```bash
aws cloudformation delete-stack --stack-name AgentCore-travelAgentStrands-default --region us-east-1
```

It prints nothing on success. Watch the result in the console's **Deleted** filter, where it reached
`DELETE_COMPLETE`. With account-wide admin credentials in your own account either route works, and the
console's dialog additionally asks you to type the stack name to confirm.
:::

**There is no `agentcore destroy`.** `agentcore destroy` answers
`error: unknown command 'destroy' (Did you mean deploy?)`. Run `agentcore --help` for the current
command list; it is long (about 30 commands, `deploy`, `invoke`, `logs`, `status`, `remove`,
`telemetry`, `traces` and more) and it changes between CLI releases, so treat any list here as a
snapshot.

**And `agentcore remove` is not an AWS teardown**, which is the part that matters. It carries about
twenty subcommands, and they include tempting names like `evaluator`, `online-eval`, `runtime-endpoint`
and `gateway`. They all edit the **project config** rather than the deployed resources:
`agentcore remove online-eval --help` describes itself as "Remove an online eval config **from the
project**". So removing something here does not delete the Online Evaluation Config in your account,
and it does not delete the Runtime's CloudFormation stack.

So delete the stack, and treat the CLI as a way to tidy the project afterwards:

```bash
cd /workshop/edd-workshop/travel-agent-strands
agentcore status            # confirm what is deployed before you delete it
```

**5. The root stack.** This takes down the Code Editor EC2 instance, its security group, and
the roles the bootstrap created. Roughly 5 minutes.

:::alert{type="info" header="You cannot list stacks from the Code Editor terminal"}
The Code Editor's `EditorRole` is scoped to the workshop's own resources, so an
account-wide `aws cloudformation describe-stacks` comes back
`AccessDenied: not authorized to perform: cloudformation:DescribeStacks`. That is expected,
not a broken environment. Use the CloudFormation console for the stack deletions, or
credentials with account-wide read.
:::

**What nothing above deletes:**

- **Path A only: the `CDKToolkit` stack.** `agentcore deploy` is a CDK wrapper, so its first run
  bootstraps CDK into the account and that bootstrap is a separate stack nobody tells you about.
  Inspected on a live account, it holds an S3 staging bucket plus its bucket policy, an ECR repository
  (`cdk-hnb659fds-container-assets-<account>-<region>`), five IAM roles (`cfn-exec`, `deploy`,
  `file-publishing`, `image-publishing`, `lookup`) and an SSM parameter. Nothing in it costs much at
  rest, but it survives every step above and it is shared by anything else using CDK in that account,
  so delete it only if this workshop was the only CDK user.
- The account-level `aws/spans` log group and the X-Ray Transaction Search setting. Transaction
  Search is account-wide and charges for ingestion, so turn it off deliberately if you enabled
  it just for this workshop.
- The Workshop Studio assets bucket (`ws-assets-us-east-1`), which is not yours.
- Any Bedrock model access you enabled.

**Confirm you are clean.** With account-wide credentials:

```bash
aws bedrock-agentcore-control list-online-evaluation-configs --region us-east-1 \
  --query 'onlineEvaluationConfigs[].[onlineEvaluationConfigId,status]' --output text

aws bedrock-agentcore-control list-evaluators --region us-east-1 \
  --query 'evaluators[].evaluatorId' --output text | tr '\t' '\n' \
  | grep -E 'TrajectoryCompliance|edd_workshop' || echo "clean: no workshop evaluators left"
```

The first should print nothing. The second should print
`clean: no workshop evaluators left`.

The second command matches **your** evaluator names rather than trying to exclude the managed
ones, because the account carries more managed evaluators than you might expect: alongside the
`Builtin.*` family there is a `ThirdParty.*` family (`ThirdParty.DeepEval.Bias`,
`ThirdParty.DeepEval.Toxicity`, `ThirdParty.AutoEval.Humor` and a dozen more). They are
AWS-managed, always present, and not yours to delete, so a bare listing is never empty and
proves nothing either way.

## Where to go from here

- **Add more cases**. The workshop's 6 cases barely scratch the surface of itinerary constraints. Add multi-city itineraries, accessibility constraints, dietary restrictions on the dining agent.
- **Custom evaluators**. Deploy with `EvaluatorMode=Custom` and a domain-specific rubric. Score against your team's actual quality bar, not generic helpfulness.
- **Multi-judge**. Run TWO LLM-judges with different models and surface disagreements. Disagreement is signal.
- **Apply EDD to your existing agent**. Pick a single specialist tool on your team's roadmap. Apply the wire-up Power. Apply the EDD-driven-dev Power. Release one iteration with both lenses green. That is the smallest viable adoption path.

:::alert{type="success" header="You now have the discipline to ship agents with confidence"}
Every change to your agent, a new model, a prompt tweak, an added tool, now has a verifiable before-and-after across both the content and trajectory lenses. Deploy safely.
:::
