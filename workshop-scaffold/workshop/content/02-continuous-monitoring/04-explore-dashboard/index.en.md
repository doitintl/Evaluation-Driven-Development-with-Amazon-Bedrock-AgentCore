---
title: "2.4 Explore the GenAI Observability dashboard"
weight: 40
---

## Open the GenAI Observability Console

The most reliable way is the left nav (deep-link URLs sometimes bounce back to the CloudWatch home page): in the AWS Console open **CloudWatch**, then in the left navigation expand **GenAI Observability → Bedrock AgentCore**.

The direct URL is:

```
https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#gen-ai-observability/agent-core
```

:::alert{type="info" header="Landed on the CloudWatch overview instead?"}
The older `#gen-ai-observability:tab=runtimes` link (and some deep links in a **cross-account / central monitoring** account) redirect to the CloudWatch home page. If that happens, ignore the URL and use the left nav: **GenAI Observability → Bedrock AgentCore**. The tab you want is labelled **Bedrock AgentCore**, not "Runtimes".
:::

## Walk through the dashboard

### 1. Agent overview

You will see your agent listed (e.g., `travel-agent-edd-workshop`). Click on it to open the agent detail view.

![AgentCore Observability Console](/static/images/module-2/agentcore-observability-dashboard.png)

**Expected result, your evaluator is registered and active.** Before drilling into sessions, confirm your Online Evaluation Config shows as **ACTIVE**. This is the config you deployed in step 2.2, it's what drives the automated scoring:

![Expected result: the Online Evaluation Config listed as ACTIVE](/static/images/module-2/eval-configs-active.png)

### 2. Agent dashboard

The agent's **Overview** tab shows, in order:

- **Top deltas in evaluator scores**: score trends, empty until your first scores land
- **Top spans by errors**: every span name with its trace count, tokens, errors and `Avg. span latency (ms)`
- **Sessions, invocations and errors** over time
- **FM token usage**, then **Cost usage and trends**, **Model cost ($)** and **Avg cost per trace ($)**
- **Endpoint details**

There is no p50/p90/p99 latency widget here: latency is per-span in the errors table and
per-session on the **OTEL sessions** tab. The other tabs are **Evaluations**, **OTEL
sessions**, **Traces** and **Spans**.

:::alert{type="info" header="Score widget may be sparse at low volume"}
With only 3 invocations, the "Top deltas in evaluator scores" widget may show minimal data. The widget becomes more useful as you accumulate sessions over time.

If the per-agent **Evaluations** widget ever reads **"No evaluation configurations to display"** while your config is `ACTIVE`, do not treat it as failure: the widget can lag at low volume and short time ranges. The evaluation-results **log group** (step 2.3) is the source of truth for whether scoring actually happened.
:::

### 3. Evaluations tab

Click the **Evaluations** tab. It opens with an **Evaluation configuration metrics** table, where
`Builtin.Helpfulness` shows a `Results count` alongside `Errors` and `Throttles`: that count is the
quickest confirmation that scoring is really happening.

Below it the results split into three buckets, and only the middle one fills. Scores land as **trace**
evaluations, so read **Trace evaluations**, not **Session evaluations**. Measured on a live account with
six scored sessions:

```
Session evaluations (0)
Trace evaluations (6)
Span evaluations (0)
```

Two zeros and one real number is the normal shape, not a missing-data bug, because
`Builtin.Helpfulness` is a trace-level evaluator. Your own number is however many sessions have been
scored so far, which includes Module 1's runs if you came here soon after them (see the box on step
2.3), so do not expect it to equal the three invocations from that page.

### 4. OTEL sessions tab

Click the **OTEL sessions** tab to see individual sessions. The columns are:

- Session ID
- Traces
- Total tokens
- Token cost
- Errors
- Throttles
- Avg. trace latency (ms)

Note what is **not** here: there is no per-session evaluation-score column, and no
timestamp or duration column. Click a session to drill into its traces and the full
conversation, but for the judge's score and explanation use the **Evaluations** tab or
the evaluation-results log group from step 2.3.

### 5. Evaluation results in the log group

The judge's explanation only lives in the evaluation-results log group, so that is where
you read the full text:

![Evaluation Results](/static/images/module-2/evaluation-results-log-events.png)

This view lets you:
- Spot sessions that scored low and investigate why
- Track score trends over time (are new deployments improving quality?)
- Compare scores across different time windows

## What you're seeing

The dashboard brings together everything you wired up:

| Data source | Where it came from | What it shows |
|---|---|---|
| Traces | Module 1 OTEL instrumentation | Latency, tool calls, span hierarchy |
| Log events | Module 1 `invoke_agent` log record | Session transcript (input + output) |
| Evaluation scores | Module 2 evaluator (this module) | Automated quality score per session |

All three surfaces are joined by `service.name` plus a session id. On Path B your adapter sets
both. On Path A the sidecar stamps `service.name` and Runtime assigns the session id, which is how
the console can list your sessions even though the spans carry no `session.id` attribute (the box in
Path A.4).

## Key takeaway

You now have **continuous, automated quality monitoring** without writing a single line of evaluation code. Every session your agent handles gets scored and surfaced in a single dashboard. No human needs to read transcripts to know whether quality is trending up or down.
