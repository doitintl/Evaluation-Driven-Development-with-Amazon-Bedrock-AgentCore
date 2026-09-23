---
title: "Evaluation-Driven Development for AI Agents on Amazon Bedrock AgentCore"
weight: 0
---

This workshop teaches **Evaluation-Driven Development (EDD)** for AI agents using a TypeScript travel-planning agent as the running example.

In the next 3.5 to 4.5 hours you will:

1. **See** what your agent is doing by wiring it into Amazon Bedrock AgentCore Observability (traces + structured logs).
2. **Know** when quality drops by connecting an automated LLM-judge that scores every session.
3. **Catch** where it regresses by adding trajectory-aware evaluation that sees the agent's internal reasoning path.
4. **Close the loop** by pulling production patterns back into your test suite so ground truth stays fresh.

The story is told through a **Coordinator agent for the fictional city of Luminara**. The Coordinator orchestrates three specialist tools: `query_sites` (attraction lookup), `plan_route` (multi-day itinerary planner), and `suggest_dining` (restaurant suggestions). Itinerary constraints (the Grand Museum closed on Monday, the Royal Palace closed on Tuesday with advance booking, the Night Market open only Friday through Sunday evenings, the Harbor Cruise needing advance booking) make the agent's *trajectory* matter, not just the final answer.

:::alert{type="info" header="Learn: what makes something an agent, and why trajectory matters"}
New to agents? This is the whole idea in four sentences.

An ordinary program follows a path you wrote. An **agent** is an LLM that is given
a set of **tools** (functions it may call) and decides *for itself* which to call,
in what order, and when it has finished. The sequence of calls it actually made on
one run is its **trajectory**.

Nobody writes that sequence, so nobody can fully predict it. Two runs of the same
request can take different paths, and here is the part that makes evaluation hard:
**a wrong path can still produce a right-looking answer.** An agent that skips the
opening-hours lookup and guesses can write a confident itinerary that sends someone
to a museum on the day it is closed.

That is why this workshop scores the path as well as the answer. Checking only the
final text means you find out from a customer.
:::

## Why EDD?

You cannot ship agents reliably with guesses. Every production-bound agent must answer four questions with a number, and EDD answers them progressively across the four modules:

| Module | Question it answers | How EDD answers it |
|---|---|---|
| 1. Agentic Observability | *What happened?* | OTEL traces + structured logs |
| 2. Continuous Monitoring | *Was the agent good?* | AgentCore Online Evaluation (LLM-as-Judge) |
| 3. Trajectory Evaluation | *What specifically broke?* | Framework eval: the two-lens model |
| 4. Production-to-Dev Ground Truth | *What should "good" even look like?* | Production data → fresh test cases |

The heart of the workshop is that third question. A single "is it good?" score hides *what* regressed, so EDD scores every run through **two independent lenses**:

- **Content lens** (LLM-as-Judge): was the final answer correct and helpful?
- **Trajectory lens** (tool-call matcher): did the agent take the right path to get there?

An agent can pass one lens and fail the other: a perfect-looking itinerary built by skipping a required constraint check, or a correct tool sequence that produces an incoherent answer. You need both lenses to catch both failure modes, and you'll build them up module by module.

## What's already deployed for you

When you launched the workshop, [AWS CloudFormation](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/Welcome.html) (the AWS service that creates resources from a template file) stood up only the **bootstrap** infrastructure:

- **Code Editor EC2**: VS Code in your browser with the `travel-agent/` (pi-mono TS) and `travel-agent-strands/` (Strands Python) repos cloned and dependencies pre-installed.
- **VPC + subnets** for the Code Editor.

**The AgentCore Observability + Evaluation infrastructure is NOT pre-deployed**: you deploy it yourself across Modules 1 and 2.

You'll find your Code Editor URL on the **Event dashboard** in the Workshop Studio left navigation, which lists the stack outputs directly.

## What you'll build

| Module | Time | Persona | What you do | The "aha" |
|---|---|---|---|---|
| 0. Setup | 10 min | Any | Run the agent, confirm it answers Luminara questions | "The agent works: now wire it up" |
| 1. Agentic Observability | 20-45 min | Any | Pick Path A (Strands) or Path B (any framework), deploy obs CFN, wire OTEL, verify traces | "Now we can SEE every tool call and response" |
| 2. Continuous Monitoring | 25 min | DevOps | Deploy evaluator, generate traffic, verify scores in the dashboard | "Now we KNOW when quality drops: automatically" |
| 3. Trajectory Evaluation | 90-110 min | Developer | Model swap + prompt change experiments with dual-lens scoring, then your matcher deployed as an online evaluator | "Trajectory catches what the content judge misses" |
| 4. Ground Truth Loop | 60-75 min | Agentic coding | Pull production data, wire new tool, generate test cases from real traffic | "Production informs dev, dev improves production" |

Module 3 is the long one because page 3.4 waits on real Online Evaluation results; its index page
explains how to collapse two 20-25 minute waits into one.

## Learning objectives

By the end of this workshop, you will be able to:

1. **Wire** any AI agent, Strands on the managed AgentCore Runtime, or any other framework via an OpenInference adapter, into Amazon Bedrock AgentCore Observability so every invocation produces structured traces and records.
2. **Monitor** that traffic continuously with AgentCore Online Evaluation, using either `Builtin.Helpfulness` or a custom LLM-as-Judge with a domain-specific rubric.
3. **Evaluate** model swaps and prompt changes with trajectory-aware scoring, using both pre-deploy framework evals and post-deploy Online Eval.
4. **Close the loop** by extracting production patterns into your test suite using coding-agent Powers, keeping ground truth fresh as traffic evolves.

## Learning outcomes

After completing the workshop you will have:

- A working Coordinator agent emitting AgentCore-compatible traces + log records.
- A deployed eval+obs CloudFormation stack with automated scoring.
- Hands-on experience comparing two evaluation lenses (LLM judge vs trajectory match) on the same agent.
- Production-derived test cases that complement your hand-written evaluation suite.
- A clear mental model for the EDD progression: observe → monitor → evaluate → ground-truth.

## Target audience

- AI / ML engineers building agentic systems on Amazon Bedrock.
- Application engineers integrating LLM-backed features into production services.
- DevOps / platform engineers responsible for monitoring and evaluation infrastructure.
- Developer-experience engineers responsible for evaluation discipline and CI gates.

If you have shipped at least one production-adjacent service and are comfortable reading TypeScript or Python, this workshop is for you. AgentCore experience is **not** required.

## Prerequisites

- Basic TypeScript or Python familiarity (you read code and edit configs; you do not write a new agent from scratch).
- Familiarity with the AWS CLI (`aws cloudformation deploy`, `aws logs filter-log-events`).
- An AWS-hosted event invitation and a Workshop Studio sandbox account, see [How to run this workshop](#how-to-run-this-workshop) below.
- No prior AgentCore knowledge required.

## Costs

Costs are covered by the Workshop Studio sandbox account that is provisioned for you during the event: **you do not pay for anything in this workshop**. The sandbox is automatically torn down when the event ends.

For reference, here is what gets used (all inside the sandbox AWS account):

- **Amazon Bedrock InvokeModel** for the agent (Claude Sonnet 4.6 / Haiku 4.5 / Nova Pro / Nova Lite via cross-region inference profiles) and the LLM judge, see [Amazon Bedrock pricing](https://aws.amazon.com/bedrock/pricing/).
- **Amazon Bedrock AgentCore** (Online Evaluation, Observability): see [Amazon Bedrock AgentCore pricing](https://aws.amazon.com/bedrock/agentcore/pricing/).
- **Amazon CloudWatch** logs + X-Ray Transaction Search, see [CloudWatch pricing](https://aws.amazon.com/cloudwatch/pricing/).
- **Amazon EC2** for the Code Editor (1 t3.large), see [EC2 pricing](https://aws.amazon.com/ec2/pricing/).
- **AWS Lambda** + **Amazon S3** for the workshop's deployment glue.

If you want to reproduce this in your own account after the event (not officially supported), expect single-digit-USD spend per attempt provided you destroy the stack at the end.

## How to run this workshop

:::alert{type="warning" header="AWS-run events only"}
This workshop can only be run at an AWS-hosted event through Workshop Studio. The sandbox account, scoped IAM roles, pre-deployed Code Editor EC2, and the AgentCore infrastructure are all provisioned by Workshop Studio when the event starts. **Self-paced deployment in your own AWS account is not supported.**

If you reached this page outside of an AWS-hosted event, please contact your AWS account team to request enrollment in an upcoming event.
:::

**Region: `us-east-1`** for this event. The workshop's CloudFormation, IAM, and CloudWatch resources are region-agnostic and Amazon Bedrock AgentCore is generally available in multiple AWS Regions, see [Amazon Bedrock AgentCore endpoints and quotas](https://docs.aws.amazon.com/general/latest/gr/bedrock_agentcore.html) for the current authoritative list.

The sandbox account is provisioned at no cost to you for the duration of the event. Workshop Studio also automatically tears down everything when the event ends, see [the Cleanup section in the Summary](summary/) when you finish.

---

When you are ready, head to **[Module 0: Setup](00-setup/)**.
