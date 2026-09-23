---
name: "edd-driven-agent-dev"
displayName: "EDD-Driven Agent Development"
description: "Teach a coding agent to build TypeScript pi-mono agents test-first using AgentCore Online Evaluation + a TS LLM-judge + a trajectory matcher. Defines what 'good' looks like (Cases with expected_trajectory) BEFORE writing the agent, confirms regressions are real before acting on them, and stops the loop only when both lenses agree."
keywords: ["edd", "tdd", "evaluation-driven", "agentcore", "trajectory", "llm-judge", "regression", "triage", "pi-mono", "typescript", "vitest"]
author: "EDD Workshop Team"
---

# EDD-Driven Agent Development

## Overview

This power teaches a coding agent (Kiro / Claude Code / Cursor / etc.) to **build agents the way TDD builds code**. Define what "good" looks like first, as evaluation cases with expected trajectories and a content rubric, and use those scores to drive every iteration.

The shape this power applies to is the pi-mono Coordinator-with-tools pattern in `travel-agent/`: a single Coordinator agent with N specialist tools (`query_sites`, `plan_route`, `suggest_dining`, etc.). When you add a new specialist tool, modify the system prompt, or swap the model, this power keeps you honest.

There is one thing EDD adds on top of TDD, and it changes everything: **agents are non-deterministic**. A test that fails once has not necessarily found a bug, and a test that passes once has not necessarily proved a fix. This power therefore teaches not just the loop, but the **triage discipline**: how to tell a real regression from sampling noise, how to attribute it to the change that caused it, and how to prove a fix actually fixed it.

## When to apply this power

- You're about to add a new specialist tool to the Coordinator.
- You're about to change the Coordinator's system prompt, swap a model, or add or remove a tool.
- An eval score dropped and you need to decide: real regression, or noise?
- You're hitting subjective "is this any better?" disputes after iteration.

## The EDD loop

```
1. CASES   — write 3-5 cases that span the constraint surface
2. RUBRIC  — write the LLM-judge rubric (what "good" looks like in words)
3. WIRE    — confirm the agent is instrumented for AgentCore Observability
4. RUN     — run the framework eval — get a baseline
5. ITERATE — make ONE change, re-run, TRIAGE any delta (see playbook below)
6. SHIP    — let Online Eval keep watching in production (drift detector)
```

The hard rule: **never iterate without a number to compare.** If you cannot run the eval, fix that first.

## The two-lens model

You need both lenses. They catch different bug classes.

| Lens | Catches CONTENT regressions | Catches TRAJECTORY regressions |
| --- | :---: | :---: |
| LLM-as-Judge (online or offline) | yes | no, judge cannot see the path |
| Trajectory match | no, trajectory can be perfect with a bad summary | yes |

The classic killer: a model follows the correct trajectory but generates an incoherent itinerary. Trajectory match passes, judge fails.

The quieter killer: a model produces a beautiful itinerary by skipping a constraint check and getting lucky on mock data. Trajectory match fails, judge passes. In production, that "got lucky" turns into a customer complaint when the data shifts. Trajectory matching catches it pre-deploy.

## Step 1: write CASES

Each case lives in `travel-agent/eval/cases.ts` and has the shape `Case` defined in that file. A minimal case (this compiles against the real `Case` interface — copy it as a starting point):

```typescript
{
  name: "luminara_grand_museum_monday",
  prompt: "Plan a 2-day Luminara trip arriving Monday focusing on history. I want to see the Grand Museum.",
  expected_trajectory: ["query_sites", "plan_route", "suggest_dining"],
  trajectory_match: "superset",
  rubric:
    "The Grand Museum closes on Monday. The itinerary MUST schedule the Grand Museum on day 2 (Tuesday), or it MUST explicitly state the closure conflict and offer an alternative day. The Coordinator MUST NOT schedule the Grand Museum on Monday day 1.",
  must_not_contain: ["Day 1: Monday", "Monday | Grand Museum"],
}
```

`trajectory_match` must be one of the four modes defined in `eval/cases.ts` (`TrajectoryMatchMode`). Choosing the right mode IS part of case design:

| Mode | Meaning | Use it when | Industry equivalent |
| --- | --- | --- | --- |
| `superset` | every expected tool appears at least once; extras OK | default for "the agent must consult X before Y matters less than consulting X at all" | Strands `any_order`, AgentCore TrajectoryAnyOrderMatch, LangSmith Superset |
| `in_order` | expected tools appear as a subsequence; extras between OK | ordering carries the lesson (e.g. `query_sites` BEFORE `plan_route` so closures are known) | Strands `in_order`, AgentCore TrajectoryInOrderMatch |
| `exact` | actual sequence equals expected exactly | tight contracts; brittle — use sparingly | Strands `exact_match`, AgentCore TrajectoryExactOrderMatch, LangSmith Strict |
| `subset` | agent calls ONLY tools from the expected set | catches over-planning/thrashing on scoped requests ("just tell me where to eat") | LangSmith Subset |

Optional harness assertions run alongside the judge: `must_contain: string[]` (each substring must appear, case-insensitive) and `must_not_contain: string[]` (must not appear). Use them for hard invariants the judge might be lenient about.

Coverage rubric. Aim for 5 to 8 cases that span:

1. **Happy path**, single tool. Exercises the simplest path.
2. **Multi-tool happy path**, exercises tool ordering (`in_order`: query_sites before plan_route).
3. **Constraint requiring detection**, the kill-shot for "vibes-based" agents. Forces the agent to detect a closure or advance-booking requirement and adjust.
4. **Negative-space constraint**, "no advance-booking attractions", "under $X budget", etc. Tests filtering.
5. **Scoped request** (`subset` mode), verifies the agent does NOT over-plan when the request is narrow.

Do not write cases that pass on day 1. If every case is green immediately, your rubric is too lax. Tighten until at least one case exposes a real weakness.

## Step 2: write the LLM-judge RUBRIC

The rubric is the `rubric` field on each Case. It is a free-text instruction the judge reads alongside the prompt and response. Be concrete:

- Mention specific facts the response MUST contain ("the Royal Palace requires advance booking").
- Mention specific facts the response MUST NOT contain ("the Grand Museum on a Monday").
- Avoid open-ended quality words like "good" or "comprehensive". Score them on observable invariants. Vague rubric words are the #1 source of judge-score variance — if the same response scores 0.7 one run and 0.95 the next, tighten the rubric before blaming the agent.

The judge model is configured in `travel-agent/eval/judge.ts` and defaults to `global.anthropic.claude-sonnet-4-6`. Keep the judge model FIXED across an entire experiment — the judge is your measurement instrument; changing it mid-experiment invalidates every comparison. Prefer the same model family as the AgentCore Online Eval judge so offline and online scores are comparable.

## Step 3: WIRE the agent

The Coordinator must be instrumented for AgentCore Observability before eval scores mean anything in production. This workshop wires it one of two ways (see the `byo-agentcore-evaluation` Power for the full wire-up):

- **OpenInference adapter** (Module 1 Path B — the pattern for any non-Strands framework): the agent emits `AGENT`/`LLM`/`TOOL` spans under an `openinference.instrumentation.*` scope. When you add a new specialist tool, its `TOOL` spans appear automatically — no adapter change needed. Verify:

```bash
# A TOOL span for the new tool landed in aws/spans within the last 5 minutes.
aws logs filter-log-events \
  --log-group-name aws/spans \
  --filter-pattern '"execute_tool <new_tool_name>"' \
  --start-time $(($(date +%s) * 1000 - 300000)) \
  --max-items 3 --region us-east-1 --query 'events[0].message' --output text
```

- **AgentCore Runtime** (Module 1 Path A — Strands agents): the managed sidecar emits telemetry; nothing to wire per-tool.

Also confirm the Online Eval Config exists and points at this agent's service name:

```bash
aws bedrock-agentcore-control list-online-evaluation-configs \
  --region us-east-1 \
  --query 'onlineEvaluationConfigs[].onlineEvaluationConfigName'
```

## Step 4: RUN the baseline eval

```bash
cd travel-agent
AWS_REGION=us-east-1 npm run eval -- --output results/baseline.md
```

The eval emits a markdown report with `Trajectory`, `Content score`, and per-case reasons. Save this report; it is your before-state for the next iteration. If a case is flaky at baseline (sometimes passes, sometimes fails on the SAME code), fix that first — a flaky baseline cannot detect regressions.

## Step 5: ITERATE one change at a time

A change is exactly ONE of:

- A different model (e.g. Sonnet 4.6 to Nova Lite). Set via `MODEL_ID=...` env var.
- A modified Coordinator system prompt (`src/coordinator.ts`).
- A new, removed, or renamed specialist tool (`src/agents/*.ts` plus the Coordinator's `tools: [...]` array).

Never stack two changes between evals. You will lose the signal — with two changes and one delta, causal attribution is guesswork.

After each change, re-run the same eval against the same cases, diff the report against the baseline, and **run the triage playbook on every delta**:

## The regression-triage playbook

When a case's result changed after your change, do NOT immediately revert or immediately trust it. Walk these five steps:

### 1. DETECT — is there a delta at all?

Diff the new report against the baseline. A delta is: a trajectory flip (PASS↔FAIL), a `must_contain`/`must_not_contain` flip, or a content-score move ≥ 0.15. Content moves smaller than ~0.15 on a single run are within normal judge noise — note them, don't act on them.

### 2. CONFIRM IT'S REAL — re-run the suspect case, not the whole suite

One run of one case is one sample of a non-deterministic system. Confirm before concluding:

```bash
npx tsx eval/run-experiment.ts --case 2day_history --runs 5 --output results/confirm.md
```

The stability report gives a verdict per case:

- **STABLE FAIL (0/5)** after your change, when the baseline was passing → a **real regression**. Go to step 3.
- **STABLE PASS (5/5)** → the earlier failure was sampling noise. Re-run the baseline case the same way before celebrating — if baseline is also 5/5, no regression; carry on.
- **FLAKY (k/5)** → the change made the behavior *sensitive*, which is itself a finding. Compare against the baseline's stability on the same case (run it with the old model/prompt via `MODEL_ID=...` or `git stash`). If baseline was stable and the change made it flaky, treat as a regression. If both are flaky, the CASE is under-specified — tighten the prompt or rubric first.
- Judge noise check: if trajectory is stable but the content score swings > ~0.15 across identical runs, the judge (rubric vagueness), not the agent, is the noise source. Tighten the rubric.

### 3. ATTRIBUTE — which change caused it?

Because you changed exactly one thing, attribution is usually immediate. If you broke the one-change rule, bisect: revert half the changes, re-run `--case <name> --runs 3`, repeat. Restate the causal chain out loud before fixing: "swapping to Nova Lite caused `query_sites` to be skipped on constraint-rich prompts, which broke the Monday-closure case."

### 4. LOCALIZE — what exactly went wrong?

Read the per-run detail in the report, in this order:

1. **Trajectory actual vs expected** — which tool went missing / appeared / moved? A missing `query_sites` before `plan_route` means the agent planned without closure data.
2. **The judge's reason string** — it names the rubric clause that failed ("scheduled the Grand Museum on Monday"). That clause tells you which behavior to fix.
3. **The response text itself** — confirm the judge's reason is accurate (judges can be wrong; you are the judge of the judge).

Then pick the fix layer: skipped tool → strengthen the system-prompt rule about tool use, or reconsider the model; wrong content with right trajectory → prompt wording or tool output quality; judge misjudged → fix the rubric, not the agent.

### 5. FIX and RE-VERIFY — close the loop

Apply ONE fix. Re-run the suspect case with `--runs 5` (expect STABLE PASS), then the FULL suite once (expect no new deltas elsewhere — fixes can regress other cases). A fix without a verified return to baseline is a hope, not a fix.

If instead you decide the new behavior is acceptable (e.g., a cheaper model with a known, bounded content dip), record that decision: update the case/rubric to the new bar and write one line in the report about why. Silent acceptance is how eval suites rot.

## Step 6: SHIP and monitor

Online Eval continues scoring production sessions (Module 2's config). Scores land in the evaluation-results log group as `gen_ai.evaluation.score.value`. To get paged on drift, publish the score as a metric and alarm on it:

```bash
# Find the config id, then create a metric filter on its results log group.
CONFIG_ID=$(aws bedrock-agentcore-control list-online-evaluation-configs \
  --region us-east-1 --query 'onlineEvaluationConfigs[0].onlineEvaluationConfigId' --output text)

aws logs put-metric-filter \
  --log-group-name "/aws/bedrock-agentcore/evaluations/results/${CONFIG_ID}" \
  --filter-name edd-helpfulness-score \
  --filter-pattern '{ $.["gen_ai.evaluation.score.value"] = * }' \
  --metric-transformations \
    metricName=HelpfulnessScore,metricNamespace=EDD/TravelAgent,metricValue='$.["gen_ai.evaluation.score.value"]' \
  --region us-east-1

aws cloudwatch put-metric-alarm \
  --alarm-name edd-quality-travel-agent \
  --namespace EDD/TravelAgent --metric-name HelpfulnessScore \
  --statistic Average --period 3600 --evaluation-periods 24 \
  --threshold 0.7 --comparison-operator LessThanThreshold \
  --treat-missing-data notBreaching \
  --region us-east-1
```

When the alarm fires, the production loop hands back to the dev loop: pull the low-scoring sessions from the results log group (Module 4.2's extraction), turn them into new Cases, and run this power's loop again. That is the EDD flywheel: production failures become tomorrow's regression tests.

## What this power tells the coding agent to do, every time

When asked to add or modify a specialist tool on the Coordinator, the coding agent MUST:

1. **First**, ask: "What does success look like? Show me 3 to 5 cases I can evaluate against." If the user cannot articulate this, propose Cases (with `expected_trajectory`, a valid `trajectory_match` mode from the table above, and a concrete `rubric`).
2. **Second**, write the cases BEFORE writing any agent code or prompt changes. Cases land in `travel-agent/eval/cases.ts` (or a sibling `eval/cases-<tool>.ts` the runner can import).
3. **Third**, confirm the wire-up with the observability check in Step 3.
4. **Fourth**, run `npm run eval`, paste the report into the chat. Flag any case that is flaky at baseline before proceeding.
5. **Fifth**, propose ONE change. Re-run. For every delta, run the triage playbook: confirm it is real with `--case <name> --runs 5` before reverting or accepting anything, attribute it to the change, localize via trajectory-actual + judge-reason, fix ONE thing, re-verify case-then-suite.
6. **Never** mark a task done until: (a) all cases are STABLE PASS, OR (b) remaining deltas are explicitly accepted by the user with a written justification recorded next to the case.

## When NOT to use this power

- Throwaway prototypes you will delete tomorrow.
- Pure prompt engineering for a single-question, single-turn use case.
- Where deterministic test cases are impossible (e.g. open-ended creative writing). Use Online Eval alone instead.

## See also

- `travel-agent/eval/cases.ts`, `judge.ts`, `trajectory.ts`, `run-experiment.ts` — the eval scaffold this power drives (`--case` / `--runs` live in `run-experiment.ts`).
- `../byo-agentcore-evaluation/POWER.md` — the wire-up Power (observability + Online Eval plumbing). Apply that one first for a new agent; this one for the discipline.
- `travel-agent/ARCHITECTURE.md` — the EDD-relevant failure modes for the Coordinator-with-tools pattern.
- AgentCore evaluators reference: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/evaluations.html
