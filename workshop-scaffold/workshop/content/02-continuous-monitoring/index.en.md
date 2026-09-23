---
title: "2. Continuous Monitoring"
weight: 40
---

## The problem

Module 1 wired your agent into AgentCore Observability, you can see traces, log events, and sessions in the GenAI Observability Console. But visibility alone does not tell you whether the agent's answers are *good*. You need automated quality monitoring at scale: every session scored, every regression surfaced, without a human reading transcripts.

## Persona

This module is for the **DevOps / Platform Engineer**: you deploy the evaluation infrastructure, generate traffic, and verify that automated scoring works end-to-end.

## What you'll do

1. **Understand** how Online Evaluation works (session-idle timeout, LLM judge, score delivery).
2. **Deploy** the evaluator CloudFormation stack (`agentcore-eval-and-obs.yaml`) that creates the Builtin.Helpfulness evaluator and an Online Evaluation Config watching your agent's log group.
3. **Generate traffic** by invoking the agent multiple times.
4. **Verify scores** appear in the evaluation log group (~10-15 min after your last invocation, up to 25 under judge-queue load).
5. **Explore the dashboard** to see at-a-glance quality metrics across all sessions.
6. **(Optional)** Redeploy with a **Custom evaluator** and a domain-specific rubric to see 1-5 scale scoring.

## End state

Every session your agent handles is automatically scored by `Builtin.Helpfulness` (0.0-1.0). Scores flow into CloudWatch and surface in the GenAI Observability Console without any manual intervention.

## Time

~25 minutes total (includes 10-15 minutes waiting for the first evaluation scores to arrive).

::children
