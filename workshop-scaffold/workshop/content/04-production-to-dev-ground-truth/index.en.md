---
title: "4. Production-to-Dev Ground Truth"
weight: 80
---

## The problem

The 6 cases in `eval/cases.ts` were written at launch, from developer assumptions. Production traffic has moved on: multi-city questions, accessibility requirements, budget constraints, combinations nobody anticipated. Module 2's Online Eval scores those sessions, so the low scores already tell you where ground truth is stale. Reading logs and hand-writing cases does not scale.

:::alert{type="success" header="The one idea to take away: a low-scoring session is a test case you haven't written yet"}
Move production failures into `eval/cases.ts` automatically and your suite tracks real user behaviour instead of launch-day guesses. Every case you add stops that failure coming back.
:::

## What you'll do

1. **Pull production trajectories**: query the evaluation log group for low-scoring sessions and the patterns your cases miss.
2. **Apply a wire-up Power**: have a coding agent connect a new specialist tool into the Coordinator's OTEL instrumentation.
3. **Transform production data into test cases**: convert those sessions into `Case` objects.
4. **Close the loop**: run `npm run eval` on the expanded set and verify the agent handles the new patterns.

## The loop

1. **Production traffic** reaches your agent.
2. **Online Eval scores every session** (Module 2).
3. **Low-scoring sessions are extracted.**
4. **Their patterns become test cases** (this module).
5. **The agent is fixed** to handle them.
6. **You deploy**, and those patterns are guarded from then on.

## Persona

The **Agentic coding** workflow. A coding agent queries logs, filters results, generates cases, and wires up new tools. You review its judgment calls.

## Time

~60-75 minutes. The two coding-agent pages (4.3 and 4.4) are the bulk of it: each involves a
handful of permission approvals, and 4.4 runs the framework eval two or three times at about
3 minutes per full-suite run.

::children
