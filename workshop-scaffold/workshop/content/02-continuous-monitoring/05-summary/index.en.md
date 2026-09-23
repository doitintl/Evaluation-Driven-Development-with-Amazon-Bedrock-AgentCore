---
title: "2.5 Summary"
weight: 50
---

## What you accomplished

In this module you deployed an **LLM-as-Judge** that scores every agent session automatically:

- **Deployed** the evaluator CloudFormation stack, creating the Builtin.Helpfulness evaluator and an Online Evaluation Config watching your agent's log group.
- **Generated traffic** by invoking the agent with representative queries.
- **Verified** that evaluation scores appeared in the evaluation-results log group, typically 10 to 15 minutes after the last invocation, and up to 25 when the judge queue is busy (the range step 2.3 tells you to allow).
- **Explored** the GenAI Observability dashboard to see traces, sessions, and scores in a single view.

## Key concepts

| Concept | What it means |
|---|---|
| **Builtin.Helpfulness** | Zero-config evaluator that scores content quality without custom rubric authoring |
| **Online Evaluation Config** | The watcher that picks up completed sessions and triggers the judge |
| **Session-idle timeout** | 5-minute window after last activity before the session is considered complete |
| **Evaluation log group** | Where scores land: `/aws/bedrock-agentcore/evaluations/results/<config-id>`. Note `results/`, and the config **id**, not its name. `./scripts/read-eval-scores.sh` resolves it for you. |
| **Score scale** | Set by the evaluator, not fixed. `Builtin.Helpfulness` returns 0.0-1.0 with a label like "Above And Beyond"; a custom rubric returns whatever range the rubric defines, for example 1-5 with "Very Good" at 4.0. Always read the label alongside the number. |

## Why this matters

Manual quality review does not scale. With continuous monitoring:

- Every session is scored, not just the ones you happen to read.
- Regressions surface as score drops in the dashboard, not as customer complaints.
- You can set CloudWatch alarms on score thresholds to get paged when quality degrades.

## What's next

Module 2 gave you a **smoke detector**: always-on monitoring that catches content quality issues. But `Builtin.Helpfulness` is a generic evaluator. It does not know that the Grand Museum is closed on Mondays, or that the Royal Palace requires advance booking.

**Module 3** adds trajectory-aware evaluation: custom evaluators that check whether the agent called the right tools in the right order, respecting domain constraints. This is where you catch *path regressions*: the agent gives a plausible-sounding answer but skipped a critical step.
