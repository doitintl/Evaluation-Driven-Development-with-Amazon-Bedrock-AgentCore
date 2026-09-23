---
name: edd-driven-agent-dev
description: Build and change pi-mono agents eval-first (EDD) — define Cases with expected_trajectory before coding, run the trajectory + LLM-judge eval suite, confirm regressions are real with repeated runs, and triage which change caused a score drop. Use when adding agent features, changing prompts or models, or investigating an eval-score regression.
---

# EDD-Driven Agent Development

The canonical, always-current version of this guidance is the workshop Power file. Read it in full and follow it:

```
/workshop/edd-workshop/kiro-powers/edd-driven-agent-dev/POWER.md
```

(If that path does not exist, locate `kiro-powers/edd-driven-agent-dev/POWER.md` relative to the workshop repo root — it is a sibling of `travel-agent/`.)

That file is the single source of truth shared by every coding agent in this workshop (Kiro loads it as a Power; Claude Code loads it via this skill). Follow it verbatim: write the Case (with `expected_trajectory` and a rubric) BEFORE implementing, run `npm run eval` for the loop, use `--case <substr> --runs <N>` to confirm a regression is real before acting (STABLE FAIL = real; FLAKY = tighten the case or fix sensitivity; swings < ~0.15 = judge noise), change one thing at a time, and apply the 5-step regression-triage playbook (DETECT → CONFIRM → ATTRIBUTE → LOCALIZE → FIX + RE-VERIFY) when a score drops.
