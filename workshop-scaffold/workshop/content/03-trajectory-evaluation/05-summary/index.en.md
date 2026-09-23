---
title: "3.5 Summary"
weight: 50
---

## What you learned

### Content quality and trajectory adherence are independent dimensions

A high content score does not imply the agent took the correct path, and a correct trajectory does not guarantee a well-written answer. Optimizing one can silently regress the other.

### A model swap can improve one lens and regress the other

You saw it directly: swapping the reasoning model moved trajectory behaviour one way and content quality the other. With only one lens you would have shipped a regression hidden behind a green metric.

### The framework eval is the pre-deploy CI gate

`npm run eval` runs locally in a few minutes and checks both lenses against your 6 baseline cases before any code reaches production. Unit tests for agent behaviour: fast, and repeatable enough to gate a PR once you re-run a suspicious case with `--runs 5`.

### Online Eval is the post-deploy smoke detector, for both lenses

Two evaluators now run on every production session:

| Evaluator | Lens | What it catches | Type |
|-----------|------|-----------------|------|
| `Builtin.Helpfulness`, or your 2.6 custom rubric | Content | Unhelpful answers, hallucinations, incomplete responses | LLM-as-Judge |
| `TrajectoryCompliance` | Trajectory | Skipped tools, wrong order, over-planning | Custom Code-Based (your Lambda) |

The content evaluator catches what your 6 cases didn't anticipate: novel queries, edge cases, distribution shifts. The trajectory evaluator catches tool-sequence violations on queries you never tested.

### The decision framework

| Trajectory | Content | Action |
|-----------|---------|--------|
| Green | Green | Ship. Both lenses agree the change is positive. |
| Green | Red | Investigate. The agent takes the right path but produces bad output. Likely a prompt regression. |
| Red | Green | Investigate. The answer looks good but the agent got lucky. Fix the trajectory before shipping. |
| Red | Red | Revert. Both lenses agree the change is harmful. |

:::alert{type="success" header="The rule to take back to work"}
You need both lenses agreeing on a positive delta before shipping. A single green is not enough.
:::

### The full EDD pipeline (Modules 1-3 combined)

![Two gates around every change: npm run eval blocks the PR before deploy, and Online Evaluation watches real sessions after deploy. Regressions found in production become new cases, so they are guarded from then on.](/static/images/diagrams/module3-two-gates.png)

## What comes next

Your 6 test cases were written at launch, so they encode developer assumptions about how users would behave. Production traffic shifts: users ask questions you never anticipated, hit constraint combinations you never tested, and trigger tool-call patterns your cases don't cover.

Module 4 closes the loop: pull production trajectories from Online Eval's low-scoring sessions back into your test suite, turning real-world failures into regression-preventing test cases.
