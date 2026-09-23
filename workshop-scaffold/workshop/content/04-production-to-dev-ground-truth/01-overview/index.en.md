---
title: "4.1 The ground-truth problem"
weight: 10
---

## Your cases encode assumptions, not reality

The 6 cases in `eval/cases.ts` cover what you imagined at launch: single-day trips, multi-day itineraries, dining suggestions, constraint checks. Production traffic looks different:

- **Multi-city queries**: "I'm visiting Luminara for 2 days then heading to the coast: can you plan both?"
- **Accessibility requirements**: "My grandmother uses a wheelchair, which attractions are accessible?"
- **Budget constraints**: "Plan a trip under $200 per day including dining"
- **Temporal edge cases**: "I arrive Friday at 11pm: what's still open?"
- **Negative constraints**: "Plan a trip but skip anything that requires advance booking"

Your cases cover none of these. Online Eval scores those sessions anyway, and the low scores are piling up.

## Low-scoring sessions are signals, not noise

Each one tells you something specific: the user asked a question your cases don't cover, the response was inadequate (the judge says why), or the trajectory was wrong (tools called incorrectly or not at all). That is *real user need* your suite doesn't exercise, which is what ground truth should be.

:::alert{type="success" header="The one idea to take away: triage the bottom of the distribution, not a fixed cutoff"}
In a healthy system scores cluster high (~0.8 to 1.0), so a `< 0.8` threshold finds nothing on some days and everything on others. Sort ascending and take the worst sessions, whatever their absolute score. Sessions with evaluation *errors* need attention too.
:::

## The loop: production informs dev, dev improves production

![The ground truth loop: production sessions are scored, the lowest scores and errors are extracted, they become Case objects, you fix the agent against them, and the deploy is now permanently guarded by those cases.](/static/images/diagrams/module4-ground-truth-loop.png)

Production data drives your test suite, the suite drives your agent improvements, and those go back to production to be scored again. The loop never stops; it just gets tighter.

## What you'll need

- The evaluation results log group from Module 2 (created by the `agentcore-eval-and-obs.yaml` stack)
- The `Case` interface from `eval/cases.ts`
- A coding agent to automate the extraction and transformation

## Your coding agent here is Claude Code

The Code Editor ships with **Claude Code**, already wired to Amazon Bedrock in your workshop account, so there is no login or API key to configure. Open a terminal (**Terminal → New Terminal**) and run `claude`, or use the side panel. Wherever the steps say "your coding agent" or "your AI sidebar", that's Claude Code. The same prompts work with Kiro, Cursor, or whatever you use back home.

:::alert{type="info" header="Plumbing: one knowledge base, two native formats"}
This module's expert knowledge ships as **Powers** (`kiro-powers/*/POWER.md`): Kiro's native format, and plain markdown any agent can read by path. It is also registered natively for Claude Code as **skills**: `travel-agent/.claude/skills/` holds a thin skill per Power pointing at the canonical POWER.md, so Claude Code *discovers* these capabilities automatically when run from `travel-agent/`.

Reference the Power by path (as the steps do, which works with every agent), or describe the task and let Claude Code pull in the matching skill. Same content either way; one source of truth.
:::

Next, query the log group for the raw material.
