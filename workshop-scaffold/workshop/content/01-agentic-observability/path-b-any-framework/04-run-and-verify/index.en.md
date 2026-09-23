---
title: "Path B.4 Run and Verify"
weight: 40
---

**Scenario.** Adapter written, infrastructure deployed. Nothing has been recorded
yet, because telemetry only captures invocations made after the pipeline is live.
This step produces the first real trajectory, and proves the adapter emits what
Module 2 needs.

## Invoke the Agent

First confirm the pipeline is accepting spans. If it is not, X-Ray rejects your
spans with `400 Bad Request` and they are lost permanently:

```bash
cd /workshop/edd-workshop
./scripts/verify-telemetry.sh
```

Check 1 must read `destination=CloudWatchLogs status=ACTIVE`. Check 3 failing with
"no spans" is expected right now: you have not run the agent yet.

:::alert{type="warning" header="If check 1 does not say ACTIVE"}
Expect **6 to 10 minutes** from the B.2 stack completing.
Building the adapter in B.3 normally covers this wait, so if you arrived quickly,
give it another minute and re-run.
:::

Then run the agent:

```bash
cd /workshop/edd-workshop/openinference-aws-adapter
npm start
```

Expected output:
```
[run] Agent: travel-agent-edd-workshop
[run] Session: 085b56e0-f2f9-46f8-b188-c45d8f28a00a
[run] Region: us-east-1
[run] Scope: openinference.instrumentation.pi-mono
[run] Traces → xray.us-east-1.amazonaws.com
[run] Query: "Plan a 3-day trip to Luminara with cultural sites and local dining"

--- Agent Response ---

🌟 Your 3-Day Luminara Itinerary...

[run] Flushing spans...
[run] Done.
[run] - Traces + full trajectory: CloudWatch GenAI Observability
[run] - AgentCore Online Eval scores these spans directly (Module 2)
```

:::alert{type="info" header="➡️ For your framework"}
`npm start` (which runs `tsx src/run.ts`) is the **pi-mono/TypeScript** entrypoint. For your framework you run your own entrypoint in your own language's toolchain. Everything below, the X-Ray and CloudWatch verification, is **identical for all frameworks**, because it inspects the exported OpenInference spans, not the code that produced them.
:::

## Verify: read your own trajectory

First confirm the pipeline is healthy and the records have the shape Module 2
needs:

```bash
cd /workshop/edd-workshop
./scripts/verify-telemetry.sh
```

Expect **checks 1 and 3 to pass**, and check 2 to report no log records. That is
the correct Path B shape: your adapter exports spans, not log records, so the
agent's log group stays empty and your spans in `aws/spans` are the evidence. The
script says so explicitly rather than calling it a failure.

:::alert{type="warning" header="Did Path A as well? Name the service explicitly"}
Path A's `capture-runtime-names.sh` writes `RUNTIME_SERVICE_NAME` into `config.env`, and the script
prefers that over `SERVICE_NAME`, so with no argument it verifies your **Strands Runtime**, not your
adapter. Measured on an account that did both: it reported `3 passed, 1 failed` where the failure was
"no spans in aws/spans for travelAgentStrands_travelAgent.DEFAULT", which says nothing about Path B.
Pass the Path B service name and it checks the right thing:

```bash
./scripts/verify-telemetry.sh travel-agent-edd-workshop
```

That printed `2 passed, 0 failed` plus "Spans are present and the agent log group is empty. That is
the normal Path B shape". An explicit argument wins over both variables by design.
:::

Then print the trajectory your adapter produced. `show-trajectory.sh` takes the same optional
service-name argument, and defaults the same way, so if you did Path A as well, name your service
here too:

```bash
./scripts/show-trajectory.sh travel-agent-edd-workshop
```

On a Path-B-only account the bare `./scripts/show-trajectory.sh` is equivalent. On an account that
did both, it reads `RUNTIME_SERVICE_NAME` and prints
`Trajectory for travelAgentStrands_travelAgent.DEFAULT ... No spans found.`, which looks like your
adapter failed when it did not.

Expected shape. Your counts and timings will differ, the agent is
non-deterministic:

```
  span                               kind      sec  model                          tokens in/out
  --------------------------------------------------------------------------------------------
  invoke_agent travel-agent-edd-work AGENT   41.70  -                              -/-
  llm-call-1                         LLM      0.00  -                              -/-
  llm-call-2                         LLM      0.90  us.anthropic.claude-sonnet-4-6 3/77
  execute_tool query_sites           TOOL     0.01  -                              -/-
  llm-call-3                         LLM      0.85  us.anthropic.claude-sonnet-4-6 1911/105
  execute_tool query_sites           TOOL     0.00  -                              -/-
  llm-call-4                         LLM      3.12  us.anthropic.claude-sonnet-4-6 2010/200
  execute_tool plan_route            TOOL     0.01  -                              -/-
  ...
  llm-call-9                         LLM     19.53  us.anthropic.claude-sonnet-4-6 5809/1199

  23 spans across 1 session(s)
    session 62baa681-117f-4651-a: AGENT=1 LLM=9 TOOL=13
```

Rows are ordered by span start time, so the root `AGENT` span is always first: it
opens before anything it contains. The `...` above stands in for the remaining
`llm-call-N` and `execute_tool` rows of that run.

:::alert{type="warning" header="If it says no spans found"}
The exporter batches, so give it ~30 seconds after the run and retry. If it stays
empty, `./scripts/verify-telemetry.sh` will tell you which stage is broken.
:::

**Read the three things that matter:**

1. **`AGENT=1`** with `LLM` and `TOOL` counts greater than zero. That is the three-level hierarchy a flat `invoke_agent`-only view cannot produce.
2. **Per-call token counts** on each `LLM` row. Note the last call costs far more output tokens than the tool-selection calls: cheap decisions, expensive synthesis.
3. **`session.id`** ties every span to the one run in your terminal.

:::alert{type="info" header="Plumbing: why not `aws xray get-trace-summaries`?"}
With Transaction Search enabled, OTLP spans are written to the `aws/spans` log group and are **not** returned by `xray get-trace-summaries` or `batch-get-traces`. Those commands can report nothing while your spans are present, so read `aws/spans` instead.

Query the log group instead, as above, or browse it in the console: [aws/spans log group](https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/aws$252Fspans). `aws/spans` is also the only place `input.value` and `output.value` (the tool arguments and results Module 2 scores) are visible.
:::

## Verify in CloudWatch Console

**Expected result, your agent appears in the dashboard.** After the run, the GenAI Observability dashboard lists your Path B (OpenInference) agent. If you also completed Path A, both agents converge in the *same* dashboard, the Strands agent shows as a `bedrock-agentcore` runtime and the pi-mono agent as `other`, proving both instrumentation paths reach the same evaluation-ready surface:

![Expected result: both agents converge in one GenAI Observability dashboard, with the Path A Strands agent and the Path B pi-mono (OpenInference) agent side by side](/static/images/module-1/1b-dashboard-both-agents.png)

:::alert{type="info" header="Why Path B's row reads 0 tokens and no cost"}
In the Agents table your Path B row shows **Total tokens 0** and an empty cost column,
while a Path A row shows real numbers. The same 0 appears in the trace header. Your
telemetry is fine, and you can prove it in two clicks: open the trace, select any
`llm-call-N` span, and its panel shows the model, `Input tokens`, `Output tokens` and
even a per-span `Total cost`.

The counts live on the `LLM` child spans, not on the root. Your adapter puts them there
as `llm.token_count.*`, and ingestion mirrors them into `gen_ai.usage.input_tokens` /
`gen_ai.usage.output_tokens` as well, which is why the per-span view can price them. The
root `AGENT` span your adapter emits carries no token attributes of its own, and the
agent-level rollup does not add up the children, so the table has nothing to sum.

`./scripts/show-trajectory.sh` prints the same per-call usage from the spans. Roll-ups and
per-span detail disagreeing like this is exactly the kind of seam that shows up when you
instrument a framework yourself: trust the spans, and check what a rollup is actually
reading before you believe a zero.
:::

1. In the AWS Console open **CloudWatch**, then in the left nav expand **GenAI Observability → Bedrock AgentCore** ([direct link](https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#gen-ai-observability/agent-core); if it bounces to the CloudWatch home page, use the left nav instead)
2. Click the **All traces** tab (or open your agent and its **Traces** tab)
3. Find your trace (filter by service name `travel-agent-edd-workshop`)
4. Click the trace. The **Spans** panel opens on **Tree**; click the **Timeline** toggle
   next to it for the waterfall

The timeline shows the waterfall of LLM calls and tool executions:

![X-Ray Timeline Waterfall](/static/images/1f-xray-timeline-waterfall.png)

5. Set the **Quick filter** to **All Events**. It defaults to **Agent spans**, which lists
   only `invoke_agent` and the `execute_tool` groups and hides every `llm-call-N` span
6. Click any `llm-call-N` span (`llm-call-1` is the blank one, so pick `llm-call-2` or
   later) to see its OpenInference attributes:

![OpenInference Metadata in X-Ray](/static/images/1f-xray-openinference-metadata.png)

In the span's `attributes` block you should see:
- `openinference.span.kind: "LLM"`
- `llm.model_name: "us.anthropic.claude-sonnet-4-6"`
- `llm.token_count.prompt` / `llm.token_count.completion` with actual values
- `llm.output_messages` with the model's response, including the `tool_call` it chose and
  the arguments it passed

On an `execute_tool` span you'll also see `input.value` (the tool arguments) and `output.value` (the tool result): the attributes AgentCore Evaluation reads for `ToolParameterAccuracy` and `Faithfulness` in Module 2.

**Expected result, the full OpenInference detail view.** Putting it together, a trace opened from a Path B (non-Strands) agent should show the span tree, the Trajectory graph, and the OpenInference JSON side by side. Confirm the JSON shows `scope = openinference.instrumentation.pi-mono`, `span.kind = AGENT`, the `input`/`output` values, and `service.name = travel-agent-edd-workshop`, this is the scope AWS natively evaluates in Module 2:

![Expected result: OpenInference trace detail for a non-Strands agent: span tree, Trajectory graph, and JSON showing scope=openinference.instrumentation.pi-mono, span.kind=AGENT, input/output values, service.name=travel-agent-edd-workshop](/static/images/module-1/1b-trace-openinference-detail.png)

## Understanding the Trajectory

The trace reveals the full agent reasoning process. Reading the run above:

| Span | Duration | Tokens in/out | What happened |
|------|----------|---------------|--------------|
| `invoke_agent travel-agent-edd-work` | 41.70s | -/- | The root `AGENT` span: the whole invocation |
| `llm-call-1` | 0.00s | -/- | Always blank, see the note below |
| `llm-call-2` | 0.90s | 3/77 | First real inference: the coordinator decides to call `query_sites`. 77 output tokens is just the tool-call JSON |
| `execute_tool query_sites` | 0.01s | -/- | Returns attractions with hours, closure days, prices, booking requirements |
| `llm-call-3` to `llm-call-8` | 0.83 to 3.88s | up to 5040/372 | One span per further model turn: read the last tool result, decide the next call. Input grows every turn as results accumulate |
| `execute_tool plan_route` | 0.00s | -/- | Optimized multi-day schedule respecting closures |
| `execute_tool suggest_dining` | 0.00s | -/- | Restaurants for the meal slots, often several calls from one turn |
| `llm-call-9` | 19.53s | 5809/1199 | Final synthesis: the formatted itinerary |

That run ended at `AGENT=1 LLM=9 TOOL=13`. **The `LLM` count tracks model turns, not
tool calls**: one turn can issue several tool calls, so the two numbers are not meant
to match.

:::alert{type="info" header="Why `llm-call-1` is blank in every run"}
The adapter opens an `LLM` span on every `message_start` that is not a tool result,
and the framework emits the first `message_start` for **the user's own prompt**, which
carries no model and no token usage. So `llm-call-1` is always a 0.00s span printing
`-` for model and tokens, and the first real inference is `llm-call-2`. To drop it,
skip `role === "user"` in the `message_start` case, the same way the code already
skips `"toolResult"`.
:::

:::alert{type="info" header="Cost insight"}
`llm-call-9` spends 16x the output tokens of the first tool-selecting call (1199 vs
77) and runs over 20x longer. Tool selection is cheap; synthesis is expensive. Input
tokens also climb every turn (3, then 1911, up to 5809) because each turn re-sends the
accumulated tool results. Both facts are visible in the trace and invisible in a flat
`invoke_agent`-only view.
:::

:::alert{type="success" header="What just happened: the causal chain"}
1. **Your action**: you subscribed a ~200-line adapter to the agent's lifecycle events, you changed nothing about the agent's logic.
2. **The mechanism**: each lifecycle event became an OpenInference span (`AGENT`/`LLM`/`TOOL`) under the `openinference.instrumentation.pi-mono` scope, SigV4-signed to the X-Ray OTLP endpoint; CloudWatch surfaces the same spans in `aws/spans` and the GenAI Observability dashboard.
3. **The evidence you saw**: the trace waterfall above, whose span timestamps match the invocation you just ran, and whose `execute_tool` sequence IS the agent's decision trail.
4. **The rule**: observability for agents means capturing the *trajectory*, not just the request/response pair, and once the trajectory is in spans, evaluation comes for free (Module 2 scores these exact spans).

**Falsification check:** if you had run the agent WITHOUT the adapter (Module 0 state), what would the dashboard show for this invocation, and would that mean the agent was broken? (Nothing, and no, which is why "no data" and "bad agent" are different diagnoses. You proved the pipeline, not just the agent.)
:::

## Checkpoint: 2 minutes before the summary

In a scratch file:

1. Name the exact evidence that YOUR invocation (not someone's screenshot) reached CloudWatch, which log group or dashboard, and which id ties it to your terminal run?
2. Complete the rule: "When a new tool is added to this agent, its calls will appear in the trace as ___ spans, without changing the adapter, because ___."
3. Which of your own systems has an agent whose tool decisions you currently cannot see? That's your Path B candidate back at work.

(Answer #2 is load-bearing for Module 4, where a coding agent adds new tools and you'll want them observable by default.)
