---
title: "3.3 Fix a prompt with continuous eval"
weight: 30
---

**Scenario.** A customer reports the agent suggested visiting the Grand Museum on Monday. You traced it: the Coordinator skipped `query_sites` before `plan_route`, so the route planner never learned about the Monday closure.

This is the EDD loop in motion: **change → eval → ship → keep watching.** You'll run a controlled version of it. Weaken the prompt to reproduce the regression, watch the eval catch it, restore the fix, watch the eval confirm it.

## Step 1: Read the current Coordinator prompt

In the Code Editor **Explorer**, open `travel-agent/src/coordinator.ts`. You will edit this same file in a moment, so keep the tab open.

`COORDINATOR_SYSTEM_PROMPT` **already opens with a hardened rule**, the fix a previous engineer landed after exactly this incident:

```ts
ABSOLUTE RULE, NO EXCEPTIONS:
  Before you call plan_route, you MUST first call query_sites for the
  interest categories the user mentioned. Examples:
    - User says "Plan a history-focused trip arriving Monday" → first
      call query_sites(query="history"), see Grand Museum closes
      Monday, only then call plan_route with the constraints applied.
    ...
  No exceptions. No assumptions. Never skip query_sites before plan_route.
```

Further down, under `## Important Rules`, the same intent also appears as a one-line abstract rule (`Always invoke query_sites BEFORE plan_route ...`). This step is about *why the concrete top-of-prompt version matters*, so you'll remove it, reproduce the regression, and put it back.

## Step 2: Weaken the prompt

Back up the file first, so Step 4 can restore it exactly:

:::code{language=bash showCopyAction=true showLineNumbers=false}
cd /workshop/edd-workshop/travel-agent
cp src/coordinator.ts /tmp/coordinator.ts.bak
:::

Now edit `src/coordinator.ts` and **delete the entire `ABSOLUTE RULE, NO EXCEPTIONS:` block** at the top of `COORDINATOR_SYSTEM_PROMPT`, leaving only the buried one-line rule under `## Important Rules`. Save.

## Step 3: Predict, then run the eval

With the concrete rule gone and only the buried one-liner left: which case fails first, and on which lens (trajectory or content)? Write one line down before running.

:::code{language=bash showCopyAction=true showLineNumbers=false}
npm run build
npm run eval -- --output results/before_prompt_fix.md
:::

Compare `results/before_prompt_fix.md` against a baseline run with the fix in
place. Watch the trajectory column and the average content score across all six
cases, not just one.

**Which case regresses is not deterministic.** The constraint-rich cases
(`luminara_2day_history_monday`, `luminara_3day_balanced`) are the likeliest, but a
real run may instead fail on something like `luminara_dining_focus`. The finding is
"a lens went red and the average dropped", not "this named case failed".

:::alert{type="warning" header="If the trajectory column stays at 6/6"}
Sonnet 4.6 sometimes *still* calls `query_sites` with only the buried one-liner, so a single run
can hold at 6/6. That is a finding, not a failed exercise: the hardening is a **safety margin**
on this model, and how visibly it matters moves run to run.

A measured pair on this agent, same model, prompt the only variable:

| | weakened prompt | rule restored |
|---|---|---|
| Suite trajectory | 5/6 | 6/6 |
| Suite average content | 0.75 | 0.89 |
| `dining_focus`, 5 repeated runs | **FLAKY 2/5**, content 0.00 to 0.95 | **STABLE PASS 5/5**, content 0.95 to 1.00 |

Note which case moved: `luminara_dining_focus`, not the Monday case the scenario is about. One
run of one case is a coin toss either way, so confirm the flip before believing it:

```bash
npm run eval -- --case dining_focus --runs 5 --output results/weakened_stability.md
```

Substitute the case that moved in *your* diff, and run it under **both** prompts: a verdict on
its own tells you the case is flaky, a verdict pair tells you your edit is why. A FLAKY result
is the most production-realistic outcome of all: the weakened prompt does not break the agent,
it makes the agent *unreliable*, the kind of bug that passes a one-shot demo and then fires on
a fraction of real traffic.
:::

## Step 4: Restore the fix

Restore your Step 2 backup:

:::code{language=bash showCopyAction=true showLineNumbers=false}
cp /tmp/coordinator.ts.bak src/coordinator.ts
:::

The workshop copy of the repo is a plain directory, not a git checkout, so
`git checkout src/coordinator.ts` will not work here. If you skipped the backup,
put the block back at the top of `COORDINATOR_SYSTEM_PROMPT` by hand:

```ts
const COORDINATOR_SYSTEM_PROMPT = `You are a travel planning coordinator for the fictional city of Luminara. You help users plan multi-day travel itineraries by orchestrating specialist tools.

ABSOLUTE RULE, NO EXCEPTIONS:
  Before you call plan_route, you MUST first call query_sites for the
  interest categories the user mentioned. Examples:
    - User says "Plan a history-focused trip arriving Monday" → first
      call query_sites(query="history"), see Grand Museum closes
      Monday, only then call plan_route with the constraints applied.
    - User says "Plan a 1-day itinerary that includes the Harbor
      Cruise" → first call query_sites(query="Harbor Cruise"), see
      it requires advance booking, only then call plan_route.
  No exceptions. No assumptions.

## Your Capabilities
... (rest of the original prompt) ...
`;
```

There is no rebuild step: the Coordinator imports `coordinator.ts` at process start, so the next `npm start` or `npm run eval` picks up the new prompt. No Docker rebuild, no container image roll, no ECR push. Just confirm it type-checks:

:::code{language=bash showCopyAction=true showLineNumbers=false}
# Confirm tsc still type-checks the file
npm run build
:::

:::alert{type="warning" header="If `tsc` reports errors"}
Fix the syntax before continuing: the eval run compiles the same file.
:::

**Why concrete beats abstract:** "Always call query_sites before plan_route" is abstract. The top-of-prompt version names the EXACT (interest category, day) pair and gives two worked examples, so it is concrete. The trajectory eval is what lets you *measure* that difference instead of guessing. The shipped agent keeps the concrete version, and you just proved why.

## Step 5: Run the framework eval with the fix restored (pre-deploy gate)

:::code{language=bash showCopyAction=true showLineNumbers=false}
npm run eval -- --output results/after_prompt_fix.md
:::

Diff `results/after_prompt_fix.md` against `results/before_prompt_fix.md`. A measured pair moved
the suite from 5/6 trajectory and 0.75 average content to **6/6 and 0.89**, with the recovery
concentrated in one case (`luminara_dining_focus`, which went from a 0.00 content score to
0.95). The point of the gate: you now have a **number** for "did this prompt edit help?" instead
of a guess.

Read the per-case rows, not just the average. The average moves for reasons that have nothing to
do with your edit: `luminara_3day_balanced` alone draws anywhere from 0.25 to 0.90 on identical
code, the same envelope 3.2 cites, and it has landed at 0.35 and 0.82 in runs minutes apart. That
spread is enough on its own to hide or fake a 0.1 shift in the mean.

![Prompt change before/after](/static/images/module-3/prompt-change-comparison.png)

The illustrative signal shown here: trajectory FAIL to PASS on `dining_focus`, which is also what
the measured pair above did.

:::alert{type="warning" header="If your numbers differ, or move the wrong way"}
LLM-judge content scores vary run to run even on identical code, and on Sonnet 4.6 a single run can hold at 6/6 whether or not the prompt fix is in place. When that happens the content column is the only place a difference shows, and judge noise can push it in the opposite direction from the illustration above.

Do not assume the fix regressed something. Confirm with repeated runs on the SAME
code: `npm run eval -- --case <name> --runs 5` gives a STABLE/FLAKY verdict instead
of a coin flip.

Trajectory is the **more** reliable signal, but it is not immune: across two runs of
the same code you may see a different single case fail each time. So "5/6 both runs,
different case" is a flakiness finding, not evidence your edit broke something.
Rule of thumb on this 6-case suite: a single-run average-content move under ~0.15 is
noise until repeated runs say otherwise, and a single case flipping is noise until
`--runs 5` says it is not.
:::

## Step 6: Generate live traffic (post-deploy smoke detector)

Feed Online Eval a small loop of constraint-rich queries. Use the **instrumented**
entrypoint from the Module 1 path you took, not `npm start`:

:::alert{type="warning" header="`npm start` from travel-agent/ emits no telemetry"}
`npm start` is the local dev entrypoint: it talks to Bedrock directly and exports
nothing to CloudWatch. Traffic generated that way produces **zero spans**, so Online
Eval has nothing to score and Step 7 stays empty forever. Only the two entrypoints
below are wired for telemetry.
:::

**Path A (Strands on AgentCore Runtime):**

:::code{language=bash showCopyAction=true showLineNumbers=false}
cd /workshop/edd-workshop/travel-agent-strands
for i in 1 2 3 4 5; do
  agentcore invoke "Plan a 2-day Luminara trip arriving Monday with a history focus."
  echo "---"
done
:::

:::alert{type="warning" header="Path A: this traffic comes from the deployed agent, not from your edit"}
Steps 2 to 5 edited `travel-agent/src/coordinator.ts`. Your Runtime runs
`travel-agent-strands/`, which has its own prompt in `src/coordinator.py`, so these invocations
exercise **what is deployed**, not the file you just changed. Step 7 still shows you real scores on
real traffic, which is the smoke-detector half of the loop; it just is not a measurement of this
particular edit.

That gap is the lesson rather than a workaround: a prompt change is only in production once you
deploy it. To close it on Path A, make the same edit in `travel-agent-strands/src/coordinator.py`
and redeploy before sending the loop:

```bash
cd /workshop/edd-workshop/travel-agent-strands
agentcore deploy -y      # about 2 minutes
```

On Path B the adapter runs the TypeScript agent you edited, so its traffic reflects the change with
no deploy step.
:::

**Path B (any framework, via the OpenInference adapter):**

:::code{language=bash showCopyAction=true showLineNumbers=false}
cd /workshop/edd-workshop/openinference-aws-adapter
for i in 1 2 3 4 5; do
  USER_QUERY="Plan a 2-day Luminara trip arriving Monday with a history focus." npm start
  echo "---"
done
:::

Scoring needs 15 to 25 minutes (the 5-minute AgentCore session-idle timeout, then
judging). While you wait, re-run the framework eval to confirm the prompt change broke
nothing else:

:::code{language=bash showCopyAction=true showLineNumbers=false}
npm run eval -- --output results/regression_check.md
:::

## Step 7: Check the Online Eval scores

The helper script resolves your config and its results log group for you, on either
path:

:::code{language=bash showCopyAction=true showLineNumbers=false}
cd /workshop/edd-workshop
./scripts/read-eval-scores.sh
:::

If you would rather run the raw commands, note that every workshop config name starts
with `edd_workshop_`, so that is the string to match on:

:::code{language=bash showCopyAction=true showLineNumbers=false}
EVAL_CFG_ID=$(aws bedrock-agentcore-control list-online-evaluation-configs \
  --region us-east-1 \
  --query 'onlineEvaluationConfigs[?contains(onlineEvaluationConfigName, `edd_workshop`)].onlineEvaluationConfigId | [0]' \
  --output text)

aws logs tail "/aws/bedrock-agentcore/evaluations/results/$EVAL_CFG_ID" \
  --since 30m --format short | head -10
:::

Or in the GenAI Observability dashboard: open your agent's service, then the
**Evaluations** tab.

:::alert{type="warning" header="Match on `edd_workshop`, not on the service name"}
Path A's config name contains `travelAgent` in camelCase, so a filter on
`travel_agent` matches nothing, `EVAL_CFG_ID` prints `None`, and the command becomes
`aws logs tail .../results/None`. Every config this workshop creates is prefixed
`edd_workshop_`, which matches on both paths.

`bedrock-agentcore-control list-online-evaluation-configs` also needs a recent **AWS
CLI v2** (see the version note in Module 0 setup). If your account holds several
`edd_workshop` configs from earlier runs, `[0]` may not be the one you deployed:
`./scripts/read-eval-scores.sh` avoids the guess by reading the log group out of the
live config.
:::

## What you've proved

You changed one thing, the prompt, and:

1. **The framework eval validated it pre-deploy**: trajectory recovered on the case that regressed,
   with no new regression elsewhere.
2. **Online Eval kept watching post-deploy**: real traffic, scored automatically, no manual
   orchestration. On Path B those scores cover the edit you made; on Path A they cover the deployed
   Strands agent unless you redeployed it, which is the distinction the box in Step 6 draws.

That is the EDD loop. Both lenses agreeing on a positive delta is the signal to deploy.

:::alert{type="success" header="The lasting insight"}
This is what makes agents engineerable in production. Without EDD, every prompt change is a guess. With EDD, every change has a verifiable before-and-after.
:::

## Checkpoint: 3 minutes before you move on

Answer in a scratch file. You'll reuse these when Module 4 closes the loop from production data.

1. **What did you change?** One sentence: the single variable you touched.
2. **What proved it?** The exact evidence: which case, which column, in which report file.
3. **Complete the rule:** "Whenever I change a prompt, before shipping I should ___, and I only trust a regression signal when ___."
4. **Back at work:** which prompt in your own system has a buried rule that deserves the ABSOLUTE-RULE treatment, and what eval case would prove it matters?

If you cannot fill in blank #3, re-read Step 7 of the model-swap page (the stability report). That is the piece separating EDD from running tests twice and hoping.

When ready: **[Module 3.4: Deploy trajectory evaluation to AgentCore](../04-online-trajectory-eval/)**.
