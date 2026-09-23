---
title: "2.1 How Online Evaluation works"
weight: 10
---

## Architecture

Online Evaluation sits downstream of the observability pipeline you wired up in Module 1. Here is the end-to-end flow:

![Module 2 pipeline: your agent emits spans and records into CloudWatch. When a session goes idle the Online Evaluation config picks it up, an LLM judge scores it, and the score plus explanation lands in the evaluation results log group.](/static/images/diagrams/module2-eval-pipeline.png)

## Timing

Two delays are involved after you invoke the agent:

1. **Session-idle timeout (5 minutes by default)**: AgentCore waits for the session to go idle before considering it complete. This prevents partial sessions from being scored mid-conversation.
2. **Judge scoring (~5-10 minutes)**: The evaluator invokes a judge model (Claude) to read the session transcript and produce a score + explanation.

Total: **allow up to 20-25 minutes** between your last invocation and seeing the first
score. The 10-15 minute figure above is the best case (idle timeout + judge scoring back
to back); judge-queue load routinely pushes this longer in practice. Don't assume failure
just because you're past 15 minutes.

## Builtin.Helpfulness

`Builtin.Helpfulness` is a zero-config evaluator that scores every session on a 0.0-1.0 scale:

- **1.0**: The agent's response fully addresses the user's request with accurate, relevant, and well-structured information.
- **0.5-0.9**: Partially helpful; some aspects of the request are addressed but information may be incomplete or imprecise.
- **0.0-0.4**: Unhelpful; the response is off-topic, factually wrong, or fails to address the query.

No rubric authoring required. This is the fastest way to get automated quality monitoring running.

## Custom evaluators (optional)

For domain-specific scoring, you can create a custom evaluator with your own rubric and a 1-5 scale. Custom evaluators let you define exactly what "good" means for your use case (e.g., "Did the agent respect the Grand Museum's Monday closure?"). This module focuses on the Builtin path first. Step 2.6 offers an optional hands-on with Custom mode if you have time.

## Next

In the next step you will deploy the evaluator infrastructure that watches your agent's log group and scores every session automatically.
