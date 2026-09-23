---
title: "3. Trajectory Evaluation"
weight: 60
---

## The problem

Online Eval (Module 2) scores the agent's *answer*. It cannot see the agent's *reasoning path*. A model swap can produce a beautifully written itinerary that schedules the Grand Museum on a Monday (it's closed) or books the Harbor Cruise with no advance reservation.

You need a lens for each dimension.

## The two-lens evaluation model

| Lens | Where it runs | What it catches |
|------|---------------|-----------------|
| **TS LLM-judge framework eval** (`travel-agent/eval/`) | Locally, pre-deploy. `npm run eval` runs 6 cases. | Trajectory regressions: wrong tool-call sequence, skipped constraints, hallucinated tools. |
| **AgentCore Online Eval** (Module 2) | Post-deploy, on real traffic. Sessions scored automatically. | Content regressions: unhelpful answers, hallucinated facts, incomplete responses. |

The framework eval is your pre-deploy CI gate. Online Eval is your post-deploy smoke detector.

:::alert{type="success" header="The one idea to take away: the two lenses are independent"}
Content quality and trajectory adherence move independently. A change can improve one while silently regressing the other, so a single green number is never enough. You ship when both lenses agree on a positive delta.
:::

## What you'll do

1. **Learn the matcher**: four trajectory modes (`superset`, `in_order`, `exact`, `subset`) plus how the LLM-judge scores content.
2. **Model swap experiment**: change one variable and watch the two lenses disagree.
3. **Prompt change experiment**: weaken a rule, catch the regression, restore the fix, confirm it.
4. **Deploy trajectory evaluation to AgentCore**: your matcher as a Custom Code-Based Evaluator (Lambda), scoring every production session alongside `Builtin.Helpfulness`.
5. **Decide**: when to ship, when to investigate, when to revert.

**Persona:** Developer. You run experiments, read eval output, and make ship/no-ship calls from data.

**Time:** ~90-110 minutes, including 20-25 minutes waiting for online trajectory results.

:::alert{type="info" header="Wait once, not twice"}
Page 3.4 verifies scores twice: a compliant session (Step 5) and a deliberately
non-compliant one (Step 6). Each wait is 20-25 minutes. Send **both** batches of traffic
before you start waiting and the two verdicts arrive together in one pass, which is how the
timing above is calculated.
:::

::children
