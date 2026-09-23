---
title: "3.2 Swap the model & catch regressions"
weight: 20
---

**Scenario.** Someone asks you to evaluate a different model for the agent's reasoning calls: different latency, throughput, or price. Can you swap without the agent regressing?

EDD answers that with a number instead of a guess. You'll swap one Bedrock model for another and watch both the content and trajectory scores move. Which model you pick is illustrative; the workflow is the point.

## Step 1: Read the cases

In the Code Editor **Explorer**, open `travel-agent/eval/cases.ts`.

6 cases span the constraint surface across three of the four matching modes: four `superset`, one
`in_order`, one `subset`, and no `exact` (see 3.1 for why `exact` suits pipelines rather than
agents). The interesting one here is `luminara_2day_history_monday`:

```ts
{
  name: "luminara_2day_history_monday",
  prompt:
    "Plan a 2-day Luminara trip arriving Monday focusing on history. I want to see the Grand Museum and the Royal Palace.",
  expected_trajectory: ["query_sites", "plan_route", "suggest_dining"],
  trajectory_match: "superset",
  rubric:
    "The Grand Museum closes on Monday and the Royal Palace closes on Tuesday. The itinerary MUST schedule the Grand Museum on day 2 (Tuesday) and the Royal Palace on day 1 (Monday), or it MUST explicitly state the closure conflict and offer an alternative day. The response MUST mention that the Royal Palace requires advance booking. The Coordinator MUST NOT schedule the Grand Museum on Monday day 1.",
  // No must_not_contain here, deliberately: see the comment in the file.
}
```

The Coordinator must call `query_sites` before `plan_route` so the route planner has real closure data. That rule lives in `COORDINATOR_SYSTEM_PROMPT` in `src/coordinator.ts`. Skip `query_sites` and the case fails even when the response *looks* right.

:::alert{type="info" header="Read the comment where `must_not_contain` used to be: a gate that was wrong"}
This case once carried `must_not_contain: ["Day 1: Monday", "Monday | Grand Museum"]`, and it
failed on every **correct** answer. The agent renders its itinerary as `=== Day 1: Monday ===`,
and when you arrive Monday, day 1 really is Monday, so the first string matched good output.
The second could never match anything, because the day heading and the attraction rows are on
different lines and the gate is a plain substring test.

The constraint it was reaching for ("the Grand Museum must not appear under the Monday
heading") is about **structure**, which a substring cannot express, so it lives in the rubric
instead, where the judge can see the whole itinerary. Keep `must_not_contain` for strings that
are unambiguously wrong on their own, and let the rubric carry anything positional. A gate that
fires on correct output is worse than no gate: it trains you to ignore failures.
:::

## Step 2: Confirm the baseline model

The Coordinator uses whatever `MODEL_ID` your shell exports. Your Code Editor sources `config.env` on login, which sets `MODEL_ID=us.anthropic.claude-sonnet-4-6`.

:::code{language=bash showCopyAction=true showLineNumbers=false}
echo "MODEL_ID=$MODEL_ID"
:::

## Step 3: Run the baseline eval

Pin Sonnet 4.6 explicitly so the command is reproducible:

:::code{language=bash showCopyAction=true showLineNumbers=false}
MODEL_ID=us.anthropic.claude-sonnet-4-6 npm run eval -- --output results/baseline_sonnet.md
:::

This takes ~3 to 5 minutes (6 cases x ~30s each, plus LLM-judge scoring). Open `results/baseline_sonnet.md`. Expect a trajectory pass rate of 6/6 and an average content score around 0.85 to 0.95.

An occasional 5/6 on the baseline is sampling noise, not a broken setup: across repeated
baseline runs on identical code, one case flakes roughly one run in five, and
`luminara_3day_balanced` content alone has been measured anywhere from 0.25 to 0.90. Those two
extremes came from the **same model on the same code fifteen minutes apart**, so a single number
from a single run tells you very little. That is exactly why Step 7 re-runs a case before drawing a
conclusion. Treat the numbers as a distribution, not a fingerprint.

Read it like an engineer, not a scoreboard. Two questions:

1. For `luminara_2day_history_monday`, find the `Trajectory actual` line. Which tool ran **first**, and why does that ordering matter here? (Answer: `query_sites`, because it is what gives `plan_route` the closure data. That causal link is exactly what the trajectory lens protects.)
2. Find the lowest content score and read the judge's reason. Does it cite a **specific rubric clause**, or is it vague? Those reason strings are your debugging breadcrumbs for the rest of the module.

This report is your **before-state**. Every conclusion below is a diff against it: without a baseline, a "regression" is just an opinion.

:::alert{type="info" header="Plumbing: why two evaluators in one report"}
`run-experiment.ts` runs both per case, in parallel. The LLM-judge in `judge.ts` scores response content; the matcher in `trajectory.ts` scores the tool-call sequence extracted from `agent.state.messages`.
:::

:::alert{type="info" header="Optional: what the us.* prefix means"}
The `us.` prefix on `us.anthropic.claude-sonnet-4-6` (and all `us.amazon.*` ids in this module) is the [Amazon Bedrock cross-region inference profile](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html) for the US geography. Bedrock routes the InvokeModel call to whichever US region has capacity (`us-east-1`, `us-east-2`, or `us-west-2`), which is why it works in all three. In an AP or EU region, swap `us.` for `apac.` or `eu.` (for example `eu.anthropic.claude-sonnet-4-6`).

The travel-agent's TS-side fallback in `src/utils/config.ts` is also `us.anthropic.claude-sonnet-4-6`. The env var wins.
:::

## Step 4: Swap to a different model

`MODEL_ID` is read per invocation, so there is no rebuild and no deployment step. Pick a model that differs meaningfully in size or family from Sonnet 4.6 so the lens differences are visible:

:::code{language=bash showCopyAction=true showLineNumbers=false}
MODEL_ID=amazon.nova-lite-v1:0 npm start -- "Plan a 2-day Luminara trip arriving Monday focusing on history."
:::

:::alert{type="info" header="Optional: other candidate models you can substitute"}
`amazon.nova-pro-v1:0`, `us.anthropic.claude-haiku-4-5-20251001-v1:0`, or any other Bedrock chat model your account can reach. All that matters is that the **candidate** differs from the **baseline**. Note the prefixes in pi-ai: Amazon models use `amazon.`, Anthropic models use `us.anthropic.`.
:::

## Step 5: Predict, then re-run the eval

Jot down two predictions first. A scratch file is fine; committing to a prediction is what makes the result land.

1. Will the lighter model's **trajectory** pass rate be higher, lower, or the same as 6/6? Why?
2. Will its **average content** score be higher or lower than baseline? Why?

Most people predict "everything gets worse." The real result is more interesting, and a wrong prediction is the lesson.

:::code{language=bash showCopyAction=true showLineNumbers=false}
MODEL_ID=amazon.nova-lite-v1:0 npm run eval -- --output results/candidate.md
:::

Open `results/candidate.md` and check both predictions against the numbers before reading on. A typical comparison:

![Model swap comparison](/static/images/module-3/model-swap-comparison.png)

The reliable finding: somewhere in your 6 cases, the two columns move in **opposite directions**. A lighter model can score *higher* on content for easier cases (terser reads as more direct) while regressing trajectory on a constraint-rich case. Without the trajectory lens you would ship whichever regression content alone cannot see.

:::alert{type="warning" header="If your run does not match the illustration"}
Which case fails, and by which mechanism (skipped tool call vs. different tool order vs. content-only), is **not deterministic**. Re-running the same swap can surface a different case, or a content-only regression instead of a trajectory one. The illustrative example is `luminara_2day_history_monday`, where a smaller model may skip `query_sites` and go straight to `plan_route`, but your run does not have to reproduce that to be correct.
:::

## Step 6: Compare the two reports side by side

:::code{language=bash showCopyAction=true showLineNumbers=false}
# Baseline
MODEL_ID=us.anthropic.claude-sonnet-4-6 npm run eval -- --output results/before.md

# Candidate
MODEL_ID=amazon.nova-lite-v1:0 npm run eval -- --output results/after.md

# Diff (review the two runs side-by-side)
diff results/before.md results/after.md
:::

For a visual diff, select both `results/*.md` files in the Code Editor **Explorer** and use **right-click → Compare Selected**.

## Step 7: Confirm the regression is real

One run of one case is a single sample, not a verdict. On a 6-case suite an average-content move under ~0.15 is within judge noise, and a single trajectory flip can be a coin toss. Industry practice (τ-bench's pass^k, Anthropic's eval guidance) is to re-run the suspect case several times before acting.

Take whichever case moved most in your diff and re-run just that case 5 times under the candidate:

:::code{language=bash showCopyAction=true showLineNumbers=false}
MODEL_ID=amazon.nova-lite-v1:0 npm run eval -- --case 2day_history --runs 5 --output results/confirm_candidate.md
:::

Each run prints its own `traj=`/`score=` line as it lands, and the whole set finishes in a
couple of minutes on a light model.

Substitute `--case` with a substring of the case that moved in *your* diff. Open the stability report and read the verdict line:

- **STABLE FAIL (0/5)**: the regression is real. The per-run detail shows the same tool missing every time, so it is a behavior, not luck.
- **STABLE PASS (5/5)**: your first candidate run hit sampling noise. Re-run the baseline the same way before concluding anything.
- **FLAKY (2/5, 3/5...)**: the most instructive outcome. The candidate is *sensitive* on a case where the baseline was stable. In production that is a latent incident firing on some fraction of traffic, arguably worse than a stable failure because it passes your smoke test and pages you at 2am.

:::alert{type="success" header="What just happened: the causal chain"}
1. **Your action**: changed exactly one variable (`MODEL_ID`), nothing else.
2. **The mechanism**: a lighter model follows the prompt's "call `query_sites` before `plan_route`" rule less reliably, so on some samples it plans without closure data.
3. **The evidence**: the stability report's `Trajectory actual` lines. Compare a failing run's tool list against a passing run's.
4. **The rule**: a regression is confirmed when it is *stable across repeated runs of the same input*, and attributable when *only one variable changed*. One run is not evidence; one changed variable is attribution.

**Falsification check:** if you had swapped the model AND edited the prompt in one step, what would this report tell you about which change caused the failure? (Nothing. That is why the loop forbids stacking changes.)
:::

## Decision

After confirming stability with `--runs`, your diff shows one of three patterns:

1. **Both columns improve or stay flat**: the candidate is a viable replacement. Keep Online Eval running as the smoke detector for queries you didn't anticipate.
2. **Content improves, trajectory regresses**: do not deploy. The candidate isn't following the discipline of the Coordinator's system prompt, and the response alone cannot show you that.
3. **Trajectory holds, content regresses**: tighten the prompt to give the candidate more guidance, then re-run.

Once both lenses are green, model choice becomes a normal cost / latency / quality trade-off. The eval scaffold is what gives you data to make it responsibly. Current per-token rates are on the [Amazon Bedrock pricing page](https://aws.amazon.com/bedrock/pricing/).

A single number ("is it better?") hides what is regressing. That is the workshop's core lesson: EDD splits the question into two lenses and forces a decision against each.

## Step 8: Roll back before the next module

:::code{language=bash showCopyAction=true showLineNumbers=false}
unset MODEL_ID
:::

The next `npm start` or `npm run eval` picks up the default Sonnet 4.6 inference profile again, from `config.env`, falling back to `src/utils/config.ts`.

When ready: **[Module 3.3: Prompt change](../03-prompt-change/)**.
