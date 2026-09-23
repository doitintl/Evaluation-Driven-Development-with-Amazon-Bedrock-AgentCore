---
title: "4.4 Transform production data into test cases"
weight: 40
---

Step 4.3 covered wire-up. This step applies the **case-first development loop** to a fresh specialist tool: **`time_estimator`**, which checks whether an itinerary fits the user's stated time budget. Told "I have only 4 hours on Day 1", the Coordinator calls `time_estimator` on the proposed Day 1 schedule and refuses to confirm a schedule that overruns.

## Step 1: Read the Power

In the Code Editor **Explorer**, open `kiro-powers/edd-driven-agent-dev/POWER.md`.

Its core rule: define what "good" looks like first. No agent code until you have all three:

- 5 cases that span the constraint surface.
- A rubric the LLM-judge will use.
- An `expected_trajectory` for each case.

:::alert{type="info" header="Plumbing: this Power is also a registered Claude Code skill"}
As in step 4.3, it is pre-registered for Claude Code as the native skill `edd-driven-agent-dev`, so it can be pulled in automatically. The path-reference prompt below works with any coding agent.
:::

## Step 2: Ask your coding agent to design test-first

In your AI sidebar:

> Apply the `edd-driven-agent-dev` Power at `/workshop/edd-workshop/kiro-powers/edd-driven-agent-dev/POWER.md` to design a new `time_estimator` specialist tool for the Coordinator.
>
> The tool should:
> - Accept a list of itinerary slots (each with attraction name, start time, duration in minutes) and a daily time budget in minutes.
> - Return whether the schedule fits, the total scheduled minutes, and which specific slots overrun.
> - Refuse to estimate if any slot is missing a duration.
>
> First produce 5 cases in `eval/cases-time-estimator.ts` (TypeScript, not Python) with `expected_trajectory` and a content rubric. Use `eval/cases.ts` as the schema reference, and export the array as `TIME_ESTIMATOR_CASES` so `npm run eval -- --all` picks it up. Stop and show me the cases before writing any agent code.

:::alert{type="warning" header="The export name is load-bearing"}
`eval/run-experiment.ts` imports `TIME_ESTIMATOR_CASES` from `./cases-time-estimator.js`. Any
other name and `--all` finds nothing to add: the run silently covers only the core 6 cases
and reports everything green, which is the one failure mode this module exists to prevent.
Check it before the first eval run:

```bash
grep "^export" eval/cases-time-estimator.ts
# export const TIME_ESTIMATOR_CASES: Case[] = [
```
:::

It should create `eval/cases-time-estimator.ts` with 5 Cases, **stop** for your review, and only after you approve write `src/agents/time-estimator-agent.ts`, apply step 4.3's wire-up Power, and iterate on the framework eval until trajectory and content both pass on all 5.

## Step 3: Review the cases it proposed

:::code{language=bash showCopyAction=true showLineNumbers=false}
cd /workshop/edd-workshop/travel-agent
ls -la eval/cases-time-estimator.ts && head -20 eval/cases-time-estimator.ts
:::

Expected: an `ls` listing of the file (~1-3 KB), then the first 20 lines showing the `Case` import, an array, and the start of the first case object.

Open the file and check every case has:

- A `prompt` that is a realistic Coordinator-facing request invoking the time estimator (for example, "Plan a 2-day Luminara trip but I only have 4 hours of activities per day").
- An `expected_trajectory` listing the tools the Coordinator should call (typically `query_sites`, `plan_route`, `time_estimator`).
- A `rubric` the LLM-judge can score against.

Across the 5, confirm coverage of: under-budget happy path, exact-budget edge case, single-slot overrun, multi-slot overrun, and missing-duration refusal.

If any case is missing or over-tolerant, **say no and ask for a rewrite**. That refusal is the discipline EDD enforces.

:::alert{type="warning" header="If the cases file is missing or empty"}
The coding agent stopped earlier than expected. Paste this back to it, then re-run the check:

> The cases file at `eval/cases-time-estimator.ts` is missing or empty. Please create it with 5 cases following the `Case` interface from `eval/cases.ts`, then stop and show me the result before continuing.
:::

## Step 4: Approve and let it build

Green-light the agent code. It should produce:

- `src/agents/time-estimator-agent.ts` (TypeBox schema + `AgentTool` factory in the `sites-agent.ts` shape).
- A registration line in `src/coordinator.ts`'s `tools: [...]` array.
- An entry in the Coordinator's system prompt under "Your Capabilities" saying when to call `time_estimator`.

Run the unit test after the first build:

:::code{language=bash showCopyAction=true showLineNumbers=false}
npm test -- time-estimator
:::

Then run the framework eval against the new cases plus the existing 6. **`--all` is
required**: without it the runner loads only the core 6 cases and your new
`time_estimator` cases are silently skipped, so everything passes and you learn
nothing.

:::code{language=bash showCopyAction=true showLineNumbers=false}
npm run eval -- --all --output results/time-estimator-first-pass.md
:::

Open the report. Expect **the core 6, plus whatever you merged into `eval/cases.ts` back in 4.2,
plus your 5 new ones**, and budget a couple of minutes per five cases. Walking this myself the count
was **15** (6 core + 4 mined from production + 5 time-estimator), not 11, because 4.2 step 5 says to
merge its generated cases and step 6's coding agent adds more. A count higher than 11 is the loop
working; a count of exactly 6 means `--all` did not pick up your new file, so re-check the export name
above.

:::alert{type="info" header="Which columns are gates, and which are signals"}
The report gives you four per-case verdicts, and only three of them are pass/fail:

| Column | Kind | Meaning |
|---|---|---|
| `Trajectory` | **gate** | did the tool sequence satisfy the case's match mode |
| `Must contain` | **gate** | required strings present in the answer (e.g. the total `330`) |
| `Must not contain` | **gate** | forbidden strings absent (e.g. `schedule fits` on an overrun) |
| `Content` | **signal** | the judge's 0.0-1.0 score, with a one-sentence reason |

Trajectory usually goes green almost immediately, because the rule is easy to satisfy once the
tool is registered. **The `must_contain` / `must_not_contain` columns are the ones worth
reading carefully**: they are your own assertions about the answer, so a failure there is
unambiguous and not judge-dependent.

The content score is deliberately **not** a gate in this scaffold. `eval/judge.ts` defines what
the number means, and reading it as a band is far more useful than comparing it to a cutoff:

| Band | The judge's own definition |
|---|---|
| 1.0 | rubric fully satisfied, no constraint violations |
| 0.7-0.9 | minor omissions or wording issues, no constraint violations |
| 0.4-0.6 | partial satisfaction, or a single low-severity constraint violation |
| 0.1-0.3 | major omissions, or a clear constraint violation |
| 0.0 | rubric not addressed |

So a 0.30 is not "slightly under a bar", it is the judge telling you it saw a real violation.
Read the reason string; it names which one.
:::

Have the coding agent **iterate**: for each failing case, propose ONE change (usually a system prompt clarification, sometimes a tool addition), re-run, compare deltas.

:::alert{type="warning" header="When the ONE change makes it worse, revert. That is the exercise."}
This is the most likely thing to happen, and it is not a failure of the method: it is the
method working. A real run of this page:

| | `time_estimator_after_route_planning` |
|---|---|
| First pass | content **0.55** |
| After the agent's one prompt fix | **0.30 / 0.37 / 0.40** across `--runs 3` |
| Verdict | STABLE regression, not noise |
| Action taken | **reverted the change** |
| After the revert | still **0.30** |

The agent's fix was reasonable in the abstract (require durations to come only from confirmed
`query_sites`/`plan_route` output). Adding it made the answer worse, consistently. Note the
discipline: the regression was confirmed with `--runs 3` *before* acting, so the decision to
revert rested on three samples, not one.

And note the last row, which is the honest part: reverting did **not** hand back the 0.55.
That single 0.55 was probably a lucky sample on a case whose real mean sits near 0.4. Which is
the lesson underneath the lesson: a one-run number is not a baseline, so "restore the previous
score" is not always an achievable goal. What you can do is stop making it worse, and then
judge the case on repeated runs.

So when your delta is negative:

1. Re-run the case with `--runs 3` first. A single sample cannot distinguish a regression from judge noise.
2. If it is **STABLE** worse, revert. Do not stack a second fix on top of a bad one.
3. Then ask the more uncomfortable question: is the **case** wrong? A rubric that no reasonable answer can satisfy is a bug in your ground truth, not in the agent. Tightening a vague rubric is a legitimate fix; loosening one to make a red case go green is not.

A case that resists two honest attempts is worth leaving red and documenting. Shipping with a
known, understood red is safer than shipping with a green you engineered by weakening the test.
:::

## Step 5: Promote when all green

When trajectory and content scores all clear the threshold (>=0.7 in the default rubric), the coding agent should:

1. Confirm `createTimeEstimatorAgentTool()` is registered in `src/coordinator.ts`'s `tools` array.
2. Confirm the system prompt mentions `time_estimator` under "Your Capabilities", with an example of when to invoke it.
3. Re-run the full suite (`npm run eval -- --all`) to confirm the new cases improve and the existing 6 do not regress.

No Docker rebuild, no container image roll. The Coordinator imports `time-estimator-agent.ts` at process start, so the next `npm start` picks up the new tool.

## Step 6: Audit the coding agent

You just delegated engineering work to an agent operating under a skill file. Before trusting that pattern back at work, grade it against this checklist, using your conversation and the produced files as evidence:

| # | The Power's rule | Evidence to look for | Pass? |
|---|---|---|---|
| 1 | Cases BEFORE code | **In the conversation**: it showed you the cases while `src/agents/time-estimator-agent.ts` still did not exist. Do not use file timestamps for this one, see the note below | |
| 2 | It stopped for your review | The agent paused after proposing cases instead of barreling into implementation | |
| 3 | Valid case design | Each case has a real `trajectory_match` mode (`superset`/`in_order`/`exact`/`subset`) chosen deliberately, and a rubric with observable invariants (no "good"/"comprehensive") | |
| 4 | One change per iteration | When a case failed, it proposed ONE fix, re-ran, and compared: not a batch of speculative edits | |
| 5 | Confirmed before concluding | On any flaky-looking failure, it re-ran the suspect case (`--case <name> --runs N`) rather than declaring victory/defeat off one sample | |
| 6 | Full-suite regression check | It re-ran all cases at the end and reported no collateral damage on the existing 6 | |

:::alert{type="warning" header="Rule 1's evidence is the transcript, not the filesystem"}
Two reasons file dates cannot settle rule 1. The workshop copy of the repo is a plain directory, not a
git checkout, so there are no commits to inspect. And rules 4 and 5 push the agent to *revisit the
cases* after the code exists, so the cases file legitimately ends up **newer** than the agent code.
Measured on this walkthrough: `eval/cases-time-estimator.ts` last modified **06:17:13** against
`src/agents/time-estimator-agent.ts` at **05:57:03**, purely because three rubric refinements landed
after the first eval run. Read the conversation instead: the cases were on screen, and the agent was
waiting for approval, before any agent file existed.
:::

Score it honestly. If the agent skipped #2 or #5, paste that rule from the Power back into the chat and ask it to redo that part. **A skill file is a contract, and this review is how the contract gets enforced.** It also hardens your own skills: every violation you catch becomes a sharper MUST in the skill text, the production-failure-to-test-case flywheel applied to the skill itself.

## What you've proved

The team can ship new specialist tools without a senior engineer in the loop, because the discipline (cases first, two lenses, confirm before concluding, no merging without green deltas) lives in the Power, and a human audit against that Power keeps it honest.

:::alert{type="success" header="The workshop's second lasting insight"}
EDD scales because the loop is automatable. Wire-up is mechanical (step 4.3); discipline is codifiable (step 4.4). Together they take EDD from "the senior engineer's habit" to "how this codebase ships agents".
:::

## Checkpoint: the whole loop, in your own words

Three lines in your scratch file:

1. Module 1 gave you ___ (what could you suddenly *see*?).
2. Modules 2 and 3 turned that visibility into ___ (what could you suddenly *decide*?).
3. Module 4 closed the loop by ___ (what now improves *automatically* as production runs?).

If line 3 mentions "low-scoring production sessions become new eval cases," you've got it. That flywheel is what you take home; the travel agent was just the vehicle.

**Next: [Summary](../../summary/).**
