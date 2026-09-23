---
name: byo-agentcore-evaluation
description: Wire any agent running outside AgentCore Runtime into AgentCore Observability and Online Evaluation (OpenInference AGENT/LLM/TOOL spans, service-name convention, eval config, failure localization). Use when adding a new tool to the travel agent, instrumenting an agent for CloudWatch GenAI Observability, or wiring/debugging AgentCore Online Evaluation.
---

# BYO AgentCore Observability + Online Evaluation

The canonical, always-current version of this guidance is the workshop Power file. Read it in full and follow it:

```
/workshop/edd-workshop/kiro-powers/byo-agentcore-evaluation/POWER.md
```

(If that path does not exist, locate `kiro-powers/byo-agentcore-evaluation/POWER.md` relative to the workshop repo root — it is a sibling of `travel-agent/`.)

That file is the single source of truth shared by every coding agent in this workshop (Kiro loads it as a Power; Claude Code loads it via this skill). Do not improvise the wiring from memory — the Power documents the exact span names (`invoke_agent <name>`, `llm-call-N`, `execute_tool <tool>`), the OpenInference scope, the `service.name` join key, the Online Evaluation Config schema, and a step-by-step failure-localization table. Follow its "What this Power tells the coding agent to do, every time" section verbatim, including running the Verify sequence and pasting actual outputs back to the user.
