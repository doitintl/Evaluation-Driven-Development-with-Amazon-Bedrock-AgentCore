---
title: "3.1 The two-lens evaluation model"
weight: 10
---

## What trajectory matching is

Asked to "plan me a 3-day trip", the Luminara Coordinator should call three tools in order:

1. `query_sites`: look up attractions and their constraints
2. `plan_route`: build the itinerary respecting open days and booking requirements
3. `suggest_dining`: add restaurants near the planned stops

That tool-call sequence is the *trajectory*. Trajectory evaluation checks the path the agent took, not how the final answer reads. Module 1 (Path B) showed you the same trajectory as X-Ray spans: each `llm-call-N` is a reasoning step, each `execute_tool X` an action.

![X-Ray span list showing agent trajectory](/static/images/1f-xray-span-list.png)

## The four matching modes

The modes align with [Strands](https://strandsagents.com/docs/user-guide/evals-sdk/evaluators/trajectory_evaluator/), [AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/evaluators-builtin.html), and [LangSmith](https://docs.langchain.com/langsmith/trajectory-evals) conventions:

| Mode | Meaning | Use when | Industry equivalent |
|------|---------|----------|---------------------|
| `superset` | All expected tools were called at least once (extras OK) | Order doesn't matter, you just need coverage | Strands `any_order`, AgentCore `TrajectoryAnyOrderMatch`, LangSmith Superset |
| `in_order` | Expected tools appear as a subsequence (extras between them OK) | Dependency order matters (sites → route → dining) | Strands `in_order`, AgentCore `TrajectoryInOrderMatch` |
| `exact` | Tool-call sequence matches expected exactly: no extras, no reordering | Strict compliance required (safety-critical paths) | Strands `exact_match`, AgentCore `TrajectoryExactOrderMatch`, LangSmith Strict |
| `subset` | Agent calls ONLY tools from the expected set: no unexpected tools allowed | Scoped requests where over-planning is a regression | LangSmith Subset |

One actual sequence, four verdicts:

```
Expected: [query_sites, plan_route, suggest_dining]
Actual:   [query_sites, query_sites, plan_route, suggest_dining, suggest_dining]

  superset:  PASS ✓  (all expected present)
  in_order:  PASS ✓  (q_s before p_r before s_d)
  exact:     FAIL ✗  (extra calls)
  subset:    PASS ✓  (every call is an expected tool; repeats are allowed)
```

Only `exact` objects to repeats. **`subset` is about which tools, not how many times**: it
fails only when the agent reaches for a tool that is not in the expected set.

That is what makes it the over-planning detector. Scope the expected set to the job:

```
Expected: [suggest_dining]                                    ("where should I eat lunch?")
Actual:   [query_sites, plan_route, suggest_dining]

  subset:    FAIL ✗  (unexpected tool calls: query_sites, plan_route)
```

The agent answered the question, but planned a whole itinerary to get there. On harder
requests that pattern correlates with confusion, and it costs tokens and latency on every
request.

## Two scores per case

The runner you'll use on the next page executes the 6 core Luminara cases:

```bash
cd /workshop/edd-workshop/travel-agent
npm run eval
```

Each case gets two scores, printed as a table with both columns:

1. **Trajectory score** (0 or 1): did the agent call the expected tools in the expected mode?
2. **Content score** (0.0-1.0): did the LLM-judge find the answer satisfactory against the case rubric?

(Module 4 adds a `time_estimator` tool with its own cases; once those exist, `-- --all` runs them too.)

:::alert{type="info" header="Plumbing: what is inside travel-agent/eval/"}
```
travel-agent/eval/
├── cases.ts                 # 6 test cases with expected_trajectory
├── trajectory.ts            # tool-call sequence matcher (4 modes)
├── judge.ts                 # Claude-as-judge content evaluator
└── run-experiment.ts        # CLI runner
```

Every case in `cases.ts` matches this interface exactly:

```typescript
type TrajectoryMatchMode = "superset" | "in_order" | "exact" | "subset";

interface Case {
  name: string;
  prompt: string;                    // the user message
  expected_trajectory: string[];     // expected tool-call names
  trajectory_match: TrajectoryMatchMode;
  rubric: string;                    // what the LLM-judge checks in the answer
  must_contain?: string[];           // optional substring assertions
  must_not_contain?: string[];       // optional (e.g. closure-day violations)
}
```
:::

## Why the content lens alone is not enough

Online Eval sees only the session's input and output, so it can answer "was this answer helpful?" but never "which tools ran?". Consider:

- The agent is asked about a 3-day trip including the Grand Museum.
- A model swap makes it skip `query_sites` and hallucinate the opening hours.
- The hallucinated hours happen to be correct, memorized from training data.
- Online Eval scores the session 0.9: helpful and accurate.

The trajectory lens fails that same session: `query_sites` was expected and never called. The agent got lucky. Next time it won't, and you get a production incident instead of a caught regression.

:::alert{type="success" header="The aha: a great answer can come from the wrong path"}
Only the trajectory lens catches a lucky answer. Only the content lens catches a correct path with a badly worded summary.

Agreeing lenses make the decision obvious. Disagreeing lenses mean you found something worth investigating, and Module 3's experiments are built to produce exactly those disagreements.
:::

## Step 1: Skim the 6 baseline cases

In the Code Editor **Explorer**, open `travel-agent/eval/cases.ts`.

Note how the six cases spread across the modes: **four `superset`** (coverage, order irrelevant),
**one `in_order`** (`luminara_3day_balanced`, where sites must precede route), and **one `subset`**
(`luminara_dining_only_scoped`, "I'm already at the Skyline Tower, where should I eat lunch nearby?",
the over-planning detector).

**Nothing uses `exact`, and that is the practical lesson.** One retry or one extra `query_sites`
call fails it, so `exact` belongs to deterministic pipelines rather than to an LLM deciding its own
tool calls. Note the variety of shapes too: single-tool lookups (`luminara_weekend_attractions`),
full three-tool plans (`luminara_2day_history_monday`), and a budget-constrained multi-day request
(`luminara_3day_balanced`).

Next you'll change the agent and watch these cases catch regressions Online Eval misses, and vice versa.
