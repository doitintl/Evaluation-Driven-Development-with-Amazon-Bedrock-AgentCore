---
title: "Path A.4 Invoke and verify"
weight: 40
---

**Scenario.** The agent is deployed and observability is wired, but nothing has
been recorded yet: telemetry only exists for invocations that happen *after* the
pipeline is live. This step produces the first real evidence, sessions you can
see and a trajectory Module 2 can score.

## 4.1: Confirm the pipeline is accepting spans

Do this **before** invoking. Transaction Search takes a few minutes to finish
enabling after Path A.3, and **spans emitted before it is ready are rejected and
lost permanently**. One command settles it:

```bash
cd /workshop/edd-workshop
./scripts/verify-telemetry.sh
```

Right now expect check 2 to pass (the smoke test from Path A.2 already wrote a record)
and check 3 to fail with "no spans", because you have not invoked the agent since
ingestion went live. Check 1 is the one you are waiting on: you want it reading
`destination=CloudWatchLogs status=ACTIVE`.

**If check 1 reads `PENDING`, that is the normal state this early** and the script will
report a failure for it. Nothing is broken; see the note below.

:::alert{type="warning" header="If check 1 says PENDING"}
The flip from Path A.3 is still settling. Expect **6 to 10 minutes** from the stack
completing, and `PENDING` until then is normal rather than broken.

Rather than watching it, use the time: skim [Path A.5](../05-summary/) to see
where this is heading, or open `travel-agent-strands/runtime/main.py` in the Code
Editor to see how the Coordinator is exposed to Runtime. Then re-run the command.
:::

:::alert{type="info" header="Learn: why some sessions can never be scored"}
Transaction Search indexes spans into the `aws/spans` log group only from the
moment ingestion goes live. Sessions created before that are never indexed, so
they can never be scored in Module 2, and nothing reports an error. You simply
find an empty results log group later and have to work out why.

The smoke test from Path A.2 is one of those sessions. It proved the agent works,
and it will not appear in evaluation. That is expected.
:::

## 4.2: Run a few queries

```bash
cd /workshop/edd-workshop/travel-agent-strands
agentcore invoke "What attractions are open on weekends in Luminara?"
agentcore invoke "Plan a 1-day trip starting Friday focusing on culture"
agentcore invoke "Suggest a dinner restaurant near the Royal Palace"
```

Each invocation creates a separate session in the Runtime.

## 4.3: See it in the console

This is the payoff, and the console shows it better than any command can. Open
**CloudWatch**, then **GenAI Observability** in the left nav, then **Bedrock
AgentCore** ([direct link](https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#gen-ai-observability/agent-core)).

Your dashboard should now list your agent with real session and trace counts,
where Module 0 showed an empty "before" state:

![Expected result: the GenAI Observability dashboard populated after invocation, showing the agent with session, trace and token counts](/static/images/module-1/1a-dashboard-populated.png)

:::alert{type="info" header="If the metric tiles show fewer invocations than the trace list"}
The tiles at the top are built from OTEL metrics, which roll up on a slower interval than
the trace index. Seeing 2 on a tile while the **All traces** tab already lists 3 is a
reporting lag, not lost data. Give it a minute; the trace list is the source of truth.
:::

Drill into traces and you should see one trace per invocation:

![Expected result: trace list showing one trace per invocation, each with its span count](/static/images/module-1/1a-traces-list.png)

Open any trace for the full waterfall. It opens with a **`Agent spans = true`** quick
filter applied, so the tree starts at `invoke_agent`. Click **Clear filters** to see
everything the Strands sidecar captured: `POST /invocations` at the root, then
`invoke_agent → execute_event_loop_cycle → chat` and the tool spans
(`query_sites → plan_route → suggest_dining`):

![Trace detail for one invocation. Box 1: the span tree, which is the agent trajectory. Box 2: service.name in the resource attributes, the join key Module 2 filters on](/static/images/module-1/1a-trace-waterfall.png)

**That span tree is the trajectory.** It is what Module 2's judge reads and what
Module 3 tests against. If you can see it, Module 1 has done its job.

The console also renders the same thing as a labelled **Trajectory** graph, on the trace
detail page. Worth a look now: that graph is literally the object Module 3 scores when it
asks "did the agent call `query_sites` before `plan_route`?".

## 4.4: Confirm the record shape

The console proves data arrived. This confirms it has the *shape* Module 2
depends on, which the dashboard does not show:

```bash
cd /workshop/edd-workshop
./scripts/verify-telemetry.sh
```

All checks should now pass, and the script ends with a summary line like
`4 passed, 0 failed` (section 2 makes two assertions of its own, which is why the count
is higher than the number of sections). It prints the emitted `service.name`, the record
scope, the correlation key, and a count of spans by name.

:::alert{type="info" header="Optional: what the script asserts"}
Open `scripts/verify-telemetry.sh` in the Code Editor to read it. It checks that
the trace destination is live, that the agent's log group carries a record with
both an `input` and an `output` body, that the `service.name` inside the record
matches the one you are using, and that spans for that service exist in
`aws/spans`.

The third check earns its place. Module 2 filters on the value **inside** the
record, so a mismatch produces zero scores and no error. The script compares them
so you find out now rather than in Module 2.
:::

:::alert{type="warning" header="If check 3 says no spans"}
Give the export ~30 seconds and re-run: it batches. If it stays empty, your
invocations happened before ingestion was ready. Invoke once more now that check 1
reads `ACTIVE`, then re-run. Earlier sessions do not backfill.
:::

:::alert{type="info" header="Learn: why Strands has no `session.id` attribute"}
Strands correlates a session using `traceId` rather than an explicit `session.id`
attribute. Module 2's evaluator joins on the trace, so your data is already
evaluation-ready. If you go looking for `session.id` and cannot find it, nothing
is wrong.
:::

## Observability is complete

Log records land in the agent's log group, spans reach `aws/spans`, and the
dashboard shows your trajectories. The one thing still missing is scoring: your agent's
**Evaluations** tab reads *"No evaluation configurations to display in the selected time
range"*, because no evaluator is connected yet. Module 2 fixes that.

The tool calls, arguments, and responses you just captured are exactly what the
LLM judge will read. The richer the trajectory, the more actionable the scores.
