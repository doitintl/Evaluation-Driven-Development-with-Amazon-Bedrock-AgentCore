---
title: "4.3 Apply the wire-up Power"
weight: 30
---

A new specialist tool is on the backlog: **`query_events`**, which the Coordinator calls to look up Luminara events (concerts, festivals, parades) by date. It needs wiring into the Coordinator and into AgentCore Observability, so its calls appear as nested spans alongside `query_sites`, `plan_route`, and `suggest_dining`.

You already know how from Module 1. The question here: can a coding agent do it, given the right Power?

## Step 1: Read the Power

In the Code Editor **Explorer**, open
`kiro-powers/byo-agentcore-evaluation/POWER.md`. It runs to a few hundred lines,
so read it in the editor rather than the terminal.

It is the canonical write-up of the BYO wiring pattern: the OTEL `service.name`
resource attribute, the OpenInference span kinds (AGENT / LLM / TOOL), the
online-eval config, and how to register and instrument a new specialist tool. Same
content as Module 1 Path B, packaged for a coding agent.

:::alert{type="info" header="Plumbing: this Power is also a registered Claude Code skill"}
It is pre-registered as a native **skill** named `byo-agentcore-evaluation` (via `travel-agent/.claude/skills/`, which points at the canonical POWER.md), and in Kiro the same file loads as a Power natively. One file, three consumption modes: path-reference (universal), Claude Code skill, Kiro Power.

The prompt below references the Power by file path so it works with *any* coding agent. Claude Code would find it on its own if you just described the task.
:::

:::alert{type="warning" header="If you cannot find the file in the Explorer"}
Check the Explorer is rooted at `/workshop/edd-workshop`, which is where the Code
Editor pre-extracts the repo and where shells start. `ls /workshop/edd-workshop`
in a terminal confirms the repo is there.
:::

## Step 2: Generate a starter specialist-tool skeleton

The schema, factory function, and `execute` shape mirror `src/agents/sites-agent.ts`:

:::code{language=bash showCopyAction=true showLineNumbers=false}
cd /workshop/edd-workshop/travel-agent
mkdir -p src/agents
cat > src/agents/events-agent.ts <<'TS'
import { Type, type Static } from "@sinclair/typebox";
import type { AgentTool, AgentToolResult } from "@mariozechner/pi-agent-core";

const EventsQuerySchema = Type.Object({
  date: Type.String({
    description: "Date to look up events (e.g., 'Friday' or '2026-06-12')",
  }),
});

type EventsQuery = Static<typeof EventsQuerySchema>;

export function createEventsAgentTool(): AgentTool<typeof EventsQuerySchema, unknown[]> {
  return {
    name: "query_events",
    label: "Query Events",
    description:
      "Look up Luminara events (concerts, festivals, parades) for a given date. Returns event name, time, venue, and ticket info.",
    parameters: EventsQuerySchema,
    execute: async (toolCallId, args, signal, onUpdate) => {
      // TODO: load mock events from src/data/events.ts and filter by date.
      return {
        content: [{ type: "text", text: "TODO: not implemented" }],
        details: [],
      } satisfies AgentToolResult<unknown[]>;
    },
  };
}
TS
:::

This skeleton is **intentionally incomplete**, with four gaps for the Power to fill in one pass:

- No registration in `src/coordinator.ts`. The `tools: [...]` array does not include `createEventsAgentTool()`, so the Coordinator cannot invoke it.
- No mock data in `src/data/events.ts`. The `execute` lambda has nothing to filter against.
- No tests in `test/unit/events-agent.test.ts`. No way to verify the tool in isolation.
- No mention of `query_events` in the Coordinator's system prompt under "Your Capabilities".

## Step 3: Ask your coding agent to apply the Power

Open `src/agents/events-agent.ts` in the Code Editor. Start Claude Code (**Terminal → New Terminal**, then `claude`, or use the sidebar panel).

:::alert{type="info" header="What you see on first launch, and the approvals to expect"}
The Code Editor's Claude Code is already authenticated **through Amazon Bedrock**, so there
is no API key to set: the banner reads `Sonnet 4.6 · Amazon Bedrock`.

Two things are expected and neither is a problem:

- `✗ Auto-update failed: no write permission to npm prefix` in the corner. `claude` is
  installed system-wide and your user cannot write there. Ignore it.
- Claude Code starts in **manual mode**, so it pauses for permission before each action.
  This task takes roughly **8 approvals** (reading the Power, writing three files, two
  coordinator edits, one `mkdir`, then `vitest` and `tsc`). Answering *"Yes, allow all edits
  during this session"* does not silence the rest: creating a file, editing one, and running
  a command are separate permissions.

  Pressing **shift+tab** at the start switches to `accept edits on`, which removes the
  file-edit prompts. It does **not** remove all of them: reading `POWER.md` still asks,
  because `kiro-powers/` sits outside the project directory, and every shell command still
  asks. Expect 2 or 3 prompts even in that mode.

If it looks stalled, it is almost always waiting on a prompt.
:::

Give it this prompt:

> Apply the `byo-agentcore-evaluation` Power at `/workshop/edd-workshop/kiro-powers/byo-agentcore-evaluation/POWER.md` to `src/agents/events-agent.ts`.
> The new tool should follow the same pattern as `src/agents/sites-agent.ts`. Specifically:
>
> 1. Implement `execute` to load mock events from `src/data/events.ts` (create that file with at least 5 events covering different days) and filter by the requested date.
> 2. Register the tool in `src/coordinator.ts` by adding `createEventsAgentTool()` to the `tools` array and updating the system prompt's "Your Capabilities" section to list `query_events`.
> 3. Add a unit test at `test/unit/events-agent.test.ts` that verifies the tool returns events for a known date and an empty result for a date with no events.
> 4. Print a summary of the changes made. Do not verify spans or query AWS: a later step covers that.

It should produce four artifacts (skeleton, mock data, coordinator edit, test) and confirm each compiles.

Two things worth knowing about what it does:

- It will probably touch a **fifth** file, `src/data/types.ts`, to add an event type
  alongside the existing ones. That is the right call, and Step 4's check does not look for
  it.
- The last line of the prompt matters. The Power covers observability and evaluation wiring
  end to end, so without it the agent tends to carry on into AWS and hunt for spans. It will
  not find any: the code it just wrote has not been run through an instrumented entrypoint
  yet, which is exactly what Step 5 and Step 6 are for.

  It reduces the wandering rather than eliminating it, and how visibly depends on the run. One
  measured run with the line in place still reached for `aws logs filter-log-events` on
  `aws/spans` once at the end; another finished clean, stopping at the summary with no AWS call
  at all. Both are normal. If the prompt does appear, answer **No** and tell it to stop and
  print the summary; you lose nothing, because Step 6 runs the same query later, after Step 5
  has produced a span for it to find. If it never appears, nothing is wrong.

## Step 4: Verify all four artifacts exist

:::code{language=bash showCopyAction=true showLineNumbers=false}
ls -la src/agents/events-agent.ts \
       src/data/events.ts \
       test/unit/events-agent.test.ts && \
  grep -q 'createEventsAgentTool' src/coordinator.ts && \
  echo "All 4 artifacts present and Coordinator is wired."
:::

Expected: an `ls` listing of the 3 new files (a few hundred bytes to a few KB each) followed by `All 4 artifacts present and Coordinator is wired.`

:::alert{type="warning" header="If the ls short-circuits with No such file or directory"}
The coding agent skipped a file, most often the mock data or the unit test. Paste the missing-file message back into the chat, ask it to create that file, then re-run the check.
:::

## Step 5: Verify the wire-up

Smoke-test the tool in isolation:

:::code{language=bash showCopyAction=true showLineNumbers=false}
npx tsx -e "import { createEventsAgentTool } from './src/agents/events-agent.ts'; const t = createEventsAgentTool(); console.log(t.name, '|', t.description.slice(0, 60));"
:::

Expected output: the tool **name** is `query_events`, followed by whatever description your
coding agent settled on. The name is fixed by the skeleton; the description is not, so
`query_events | Query city events happening on a specific date in Luminara` is just as correct
as the skeleton's original wording.

Run the unit test the coding agent wrote:

:::code{language=bash showCopyAction=true showLineNumbers=false}
npm test -- events-agent
:::

Expected: vitest reports the `events-agent` test file passing. The coding agent decides how many cases to write, so expect **at least two** (a positive and an empty result); more is fine and often better.

Then prompt the Coordinator with a query that should trigger `query_events`. Run it
**through your Path B adapter**, not through `src/main.ts`, because the adapter is
what exports spans and Step 6 checks for one.

First take a date out of the file the coding agent wrote, because it invented the mock dates
and you cannot know in advance whether it used day names or calendar dates:

:::code{language=bash showCopyAction=true showLineNumbers=false}
grep -m1 -A1 'date:' src/data/events.ts
:::

Then ask for that date:

:::code{language=bash showCopyAction=true showLineNumbers=false}
cd /workshop/edd-workshop/openinference-aws-adapter
USER_QUERY="Are there any events in Luminara on 2025-08-04?" npm start   # use YOUR date
:::

Expected: the response lists at least one event with its time and venue, and the run
ends with `[run] Flushing spans...`.

:::alert{type="info" header="A 'no events found' answer is also a pass"}
Ask with a relative phrase like "this Friday" instead and the agent will resolve it against
today's date, which almost never matches invented mock data. Measured: it called the tool
with `{"date":"2025-07-25"}` against data that only covered 2025-08-04 to 2025-08-09 and
answered "no events currently listed", which is a **correct** answer to the question asked.
The tool still ran, so Step 6's span still appears, and the span's `input.value` is where you
confirm which date it actually asked for.
:::

:::alert{type="info" header="Plumbing: why not `npx tsx src/main.ts` here?"}
`src/main.ts` runs the Coordinator directly, with no instrumentation, exactly as
Module 0 did. It answers correctly but emits nothing, so Step 6 would find no span
and the point of this step would be lost. The adapter imports the same Coordinator
and wraps it, which is why the new tool is observable without touching the adapter.

**Took Path A? `agentcore deploy` cannot help here, and this is worth understanding.** Your
Runtime runs `travel-agent-strands/`, a separate Python codebase with its own three tools.
The `query_events` you just added lives in the **TypeScript** agent, so it is not in the
deployed artifact and redeploying cannot put it there. Measured on a live Runtime:
`agentcore invoke "Are there any events in Luminara this Friday?"` answers with a list of
attractions from `query_sites` and never calls `query_events` at all.

Use the reference adapter, which wraps the same TypeScript Coordinator you just extended:

```bash
cd /workshop/edd-workshop/solutions/module-1/openinference-aws-adapter
npm install                       # about 10 seconds, one time
source /workshop/edd-workshop/config.env
USER_QUERY="Are there any events in Luminara on <a date from src/data/events.ts>?" npm start
```

It emits under `service.name: travel-agent-edd-workshop` rather than your Runtime's service
name, which does not matter here: Step 6 filters on the **span name**, not the service.
:::

:::alert{type="warning" header="If vitest says No test files found, exiting with code 1"}
The coding agent didn't write `test/unit/events-agent.test.ts`. Paste this back to it:

> The unit test at `test/unit/events-agent.test.ts` was not created. Please create it now, using vitest and following the same style as the existing `test/eval/trajectory.test.ts`. The test should verify that the tool returns events for a known date in the mock data, and an empty result for a date with no events.

Then re-run `npm test -- events-agent` and confirm the cases pass before continuing.
:::

## Step 6: Prove the new tool is observable

A passing unit test only proves the tool works. The Power's real promise: a new tool lands on the **observability and evaluation pipeline** with zero adapter changes. The adapter run above should have emitted an `execute_tool query_events` span:

:::code{language=bash showCopyAction=true showLineNumbers=false}
aws logs filter-log-events \
  --log-group-name aws/spans \
  --filter-pattern '"execute_tool query_events"' \
  --start-time $(($(date +%s) * 1000 - 600000)) \
  --max-items 3 --region us-east-1 \
  --query 'events[0].message' --output text | head -30
:::

Expected: a span named `execute_tool query_events`, under the
`openinference.instrumentation.pi-mono` scope, with `openinference.span.kind: TOOL`, an
`input.value` carrying the date argument, and an `output.value` carrying the events
returned. Abridged from a real run:

```json
{"name":"execute_tool query_events","kind":"INTERNAL",
 "scope":{"name":"openinference.instrumentation.pi-mono"},
 "attributes":{"gen_ai.tool.name":"query_events",
   "input.value":"{\"date\":\"Friday\"}",
   "output.value":"...Luminara Jazz Night (concert) ... Harbor Fireworks Display (festival)...",
   "openinference.span.kind":"TOOL","tool.name":"query_events",
   "session.id":"16cd673b-8781-4f15-aacd-93448ecb834a"}}
```

A trailing `None` line after the JSON is normal: `--max-items` paginates, and
`events[0].message` is empty on the page after the match.

:::alert{type="warning" header="If the span query comes back empty"}
Give the OTLP export ~10 seconds and re-run. If it is still empty, confirm the Step 5 invocation actually called `query_events`: a response answered from memory without the tool call is itself a trajectory bug worth catching.
:::

:::alert{type="success" header="What just happened: the causal chain"}
1. **Your action**: the coding agent registered one new tool. Nobody touched the adapter, the CFN, or the eval config.
2. **The mechanism**: the Module 1 adapter hooks tool-execution lifecycle events *generically*, so any registered tool's calls become `TOOL` spans under the same `openinference.instrumentation.pi-mono` scope the evaluator already watches.
3. **The evidence**: the `execute_tool query_events` span you just pulled from `aws/spans`, timestamped to the invocation you ran a minute ago.
4. **The rule**: wire-up done right is *inherited, not repeated*. Instrument the agent's lifecycle once and every future tool is observable and evaluation-ready by construction.

**Falsification check:** if the adapter had hard-coded span emission per tool (`if (tool === "query_sites") ...`), what would this check have shown for `query_events`, and who would have had to fix it? (Nothing, and a human, every single time. That's the anti-pattern the Power exists to prevent.)
:::

## What you've proved

The whole wire-up, from skeleton through Coordinator registration, unit test, and **verified observability**, is mechanical enough for a coding agent given the right context. Your 4th, 5th, and 20th specialist tool no longer cost human time to reach the eval pipeline.

**Next: [Transform production data into test cases](../04-transform-to-test-cases/)**, where the second Power (the EDD-driven-dev loop) builds a brand-new tool test-first.
