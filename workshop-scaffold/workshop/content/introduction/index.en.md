---
title: "Introduction: the EDD loop"
weight: 5
---

**In 3.5 to 4.5 hours you will build an agent that tells you when it regresses, and what specifically broke.**

Ready to start? Go straight to **[Module 0: Setup](../00-setup/)**. Everything below is context you can read now or come back to later.

:::alert{type="info" header="Who this is for, and what you need (optional reading)"}
You will get the most out of this workshop if you are an **application developer or ML engineer** who builds AI agents on AWS (in any language, any framework), owns an agent's quality after launch and not just at launch, and wants the AWS-native answer to "how do I know if my agent regressed?"

**By the end you will be able to:**

1. Wire any agent into AgentCore Observability and Online Evaluation, either Strands on the managed AgentCore Runtime or any other framework via an OpenInference adapter, so every invocation is automatically traced and scored.
2. Apply Evaluation-Driven Development to drive model swaps, prompt changes, and tool additions with eval scores rather than guesses.
3. Scale EDD across your team with ready-made coding-agent Powers, so every new agent inherits the wire-up.

**Prerequisites:** basic TypeScript or Python familiarity (the running example is TypeScript; the Strands path uses Python), comfort with the AWS CLI and reading CloudFormation templates, and a modern browser. No local installs, and no prior AgentCore or LLM-judge knowledge required.
:::

## The case for EDD

If you've shipped an LLM-powered feature, you've probably hit one of these moments:

- "Should we evaluate a different model for this workload?" and the answer was a guess.
- "I changed the prompt to fix one bug. Did it break others?" Also a guess.
- "We're getting a complaint that the agent ignored a constraint", and you cannot reproduce it.

These are evaluation problems, not LLM problems. **Evaluation-Driven Development (EDD)** treats agent quality the way TDD treats code correctness: every behavioural change is measured against a fixed bar of "good", and the bar exists *before* the change.

## The two-lens model

You'll wire two complementary evaluation lenses in this workshop. They catch different bug classes:

| | Catches CONTENT regressions (incoherent answer, hallucination) | Catches TRAJECTORY regressions (skipped check, wrong order) |
|---|:---:|:---:|
| AgentCore Online Eval (LLM-as-Judge, prod traffic, 100% sampling) | yes, this is its job | no, the judge sees only the final response |
| TS LLM-judge framework eval (curated cases plus expected_trajectory in `travel-agent/eval/`) | partial, the judge can be biased by case framing | yes, this is its job |

Each lens fails the other's test:

- A Nova Lite swap might score *higher* on the LLM-judge but *lower* on trajectory because it skipped a `query_sites` call before `plan_route` and got lucky on the mock data.
- A model that follows the *correct* trajectory but generates an *incoherent* itinerary will pass trajectory and fail content.

In production, the trajectory regression is the one you do not see. Your users do not notice their agent skipped a constraint check, until the day the data shifts and the customer is sent to the Grand Museum on a Monday (it closes Mondays).

## Why this is harder than TDD

TDD has determinism on its side: same input, same output, every time. Agents do not. Two evaluation tactics keep the variance under control:

1. **Trajectory matching with `in_order` semantics**: actual tool calls may include extras, but the expected ones must appear in order. The path is much more stable than the words.
2. **LLM-as-Judge with a numeric rubric**: fix the rubric in code, swap the agent, compare scores. The judge is a measurement instrument; you do not change it casually.

## The architecture you'll work with

![The running example: you send a prompt to the Coordinator, an LLM that chooses which of three deterministic tools to call. Each step emits a span into CloudWatch, and GenAI Observability shows the resulting trajectory.](/static/images/diagrams/architecture-overview.png)

The Coordinator and its three tools are already running before you start. You will
modify them and watch both lenses respond.

Two things to notice, because the rest of the workshop depends on them:

- **Only the Coordinator is an agent.** `query_sites`, `plan_route`, and
  `suggest_dining` are plain functions over fixed data. They make no decisions,
  which is what makes the Coordinator's choices worth evaluating.
- **Every step emits a span.** That trail is the trajectory, and it is the only
  reason a judge can later ask "did it check the constraints before planning?"
  rather than only "does the answer look nice?"

You will also run a second, local evaluation suite: `travel-agent/eval/` holds
hand-written test cases with an expected tool sequence and a scoring rubric.
You run it on demand with `npm run eval`, before deploying anything. It is the
fast pre-deploy gate; AgentCore Online Evaluation is the continuous post-deploy
one. Module 3 uses both together.

When you are ready: **[Module 0: Setup](../00-setup/)**.
