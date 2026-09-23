---
title: "4.2 Pull production trajectories"
weight: 20
---

Steps 1 to 5 extract low-scoring production sessions with scripts, so you see the data flow. Step 6 hands the same job to a coding agent. Both end in new cases in `eval/cases.ts`.

## Step 1: Find the evaluation results log group

Resolve it from the **live** Online Evaluation Config, not by listing log groups:

:::code{language=bash showCopyAction=true showLineNumbers=false}
cd /workshop/edd-workshop/travel-agent

# Which config is actually running right now
EVAL_CFG_ID=$(aws bedrock-agentcore-control list-online-evaluation-configs \
  --region us-east-1 \
  --query 'onlineEvaluationConfigs[0].onlineEvaluationConfigId' --output text)

# ...and where that config writes its scores
EVAL_LG=$(aws bedrock-agentcore-control get-online-evaluation-config \
  --region us-east-1 --online-evaluation-config-id "$EVAL_CFG_ID" \
  --query 'outputConfig.cloudWatchConfig.logGroupName' --output text)

echo "Evaluation log group: $EVAL_LG"

if [ -z "$EVAL_LG" ] || [ "$EVAL_LG" = "None" ]; then
  echo "No evaluation config found. Deploy Module 2 first, then generate traffic:"
  echo "  cd /workshop/edd-workshop/travel-agent-strands && agentcore invoke \"...\"   # Path A"
  echo "  cd /workshop/edd-workshop/openinference-aws-adapter && USER_QUERY=\"...\" npm start   # Path B"
fi
:::

:::alert{type="warning" header="Why not just take the first `/evaluations/` log group"}
Because it is usually the wrong one. Every time the Online Evaluation Config is
regenerated (the optional page 2.6 does exactly that) AgentCore creates a **new**
results log group and leaves the old ones in place, and `logGroups[0]` returns the
oldest. Measured on a live account after 2.6:

```
logGroups[0]  ..._DEFA-AhhqS6Ez4L    3 events, no trajectory scores   <- what the prefix scan picks
live config   ..._DEFA-h8MFHfGuoF   15 events, TrajectoryCompliance   <- what you want
```

Mining the stale group is a silent dead end: the triage below reports nothing to fix, and
new sessions never show up there no matter how long you wait, because they are being
written to the live group instead. `./scripts/read-eval-scores.sh` resolves this the same
way if you want to sanity-check by hand.
:::

## Step 2: Extract evaluation results

:::code{language=bash showCopyAction=true showLineNumbers=false}
# Extract evaluation results
# --output json | jq -r '.[]' gives ONE record per line. Do not use --output text
# here: it joins records with TABs, so the file becomes a single line and the
# line-based parser below silently reads nothing.
aws logs filter-log-events \
  --log-group-name "$EVAL_LG" \
  --filter-pattern '"gen_ai.evaluation.score.value"' \
  --max-items 20 \
  --query 'events[*].message' \
  --output json | jq -r '.[]' > /tmp/eval-results.jsonl

echo "records: $(wc -l < /tmp/eval-results.jsonl)"

# Preview what we got
head -3 /tmp/eval-results.jsonl | jq .
:::

Each log event contains:
- `gen_ai.evaluation.score.value`: the score, on whatever scale that evaluator uses
- `gen_ai.evaluation.name`: **which** evaluator produced this score (the key measured on live records; code that has to handle older records falls back to `gen_ai.evaluation.evaluator_id`)
- `gen_ai.evaluation.explanation`: why the judge (or the code-based check) scored it that way
- The session's input (user query) and output (agent response)
- The session ID (for correlating with trajectory data in X-Ray)

**Expected result, the production data you're mining.** Content scores (here 4.0/5.0) sit high while `TrajectoryCompliance` `FAIL` (0.0, "missing query_sites, plan_route; actual suggest_dining") flags the sessions worth turning into test cases. Those `FAIL`s are the ground-truth candidates:

![Expected result: the production evaluation records this triage mines, showing a TrajectoryCompliance FAIL (0.0, missing query_sites/plan_route), a PASS (1.0), and high content scores (4.0/5.0) side by side](/static/images/module-4/production-eval-source-data.png)

:::alert{type="success" header="Two evaluators, two scales: triage them separately"}
If you did step 3.4, every session carries **both** a content score (`Builtin.Helpfulness` 0.0-1.0, or your custom rubric 1-5) **and** `TrajectoryCompliance` (0.0/1.0, PASS/FAIL). One mixed "bottom 10" misranks everything: a trajectory `0.0` and a content `0.45` are not comparable.

Group by `evaluator_id`, then triage each group on its own terms:
- **Content evaluator**: sort ascending, take the lowest-scoring plus any errors.
- **`TrajectoryCompliance`**: every `FAIL` (score `0.0`) needs attention. No gradient to sort by.

Check both. A healthy agent writes plausible answers, so content scores cluster high and the sessions worth mining hide in the trajectory `FAIL`s.
:::

:::alert{type="warning" header="If the triage reports 0 sessions needing attention"}
**First check the record count** printed by the extraction above. If it says
`records: 1` while you know several sessions were scored, the file is not
one-JSON-per-line and the parser read nothing: re-run the extraction exactly as
written, with `--output json | jq -r '.[]'` and not `--output text`.

If the count looks right and the triage still reports 0, that is a real result and
not a failure: on a fresh account the agent runs Sonnet 4.6 against clean mock data,
so sessions score near 1.0 and there is little to mine. **You still need one bad
session to continue**, so manufacture one deliberately, the same trick Module 3.4
step 6 uses:

```bash
cd /workshop/edd-workshop/openinference-aws-adapter
MODEL_ID=amazon.nova-lite-v1:0 \
  USER_QUERY="Plan a 2-day Luminara trip focused on history, arriving Monday." npm start
```

A weaker model on a constraint-rich query tends to skip `query_sites`, which is
exactly the trajectory violation worth mining. Wait 15 to 25 minutes for the score,
then re-run the extraction above.

Worth noticing: **you had to work to produce a bad session.** That is the honest
shape of this problem in production too. Low-scoring sessions are rare, which is
precisely why an automated evaluator that never gets bored is the thing that finds
them.
:::

:::alert{type="warning" header="If filter-log-events returns zero events"}
Use `--max-items`, not `--limit`. Against these log groups the raw `--limit` API parameter can silently return zero events even when real scores exist. `--max-items` (the AWS CLI's own client-side pagination cap) reliably returns the real data.
:::

This is **real production user input**. Treat query text and judge explanations as untrusted, especially when handing them to a coding agent, and scrub any PII (names, contact details, addresses) before Step 5 commits it to a version-controlled test file.

## Step 3: Filter and extract patterns, per evaluator

The evaluation fields live under a nested `attributes` object, not at the top level. Inspect one on your own account first with `head -1 /tmp/eval-results.jsonl | jq .attributes`, then run:

:::code{language=bash showCopyAction=true showLineNumbers=false}
# Parse out lowest-scoring sessions and evaluation errors, grouped by evaluator
cat /tmp/eval-results.jsonl | python3.12 -c "
import json, sys
from collections import defaultdict

by_evaluator = defaultdict(list)
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        record = json.loads(line)
        attrs = record.get('attributes', {})
        score = attrs.get('gen_ai.evaluation.score.value')
        error = record.get('error')
        evaluator = attrs.get('gen_ai.evaluation.name', 'unknown')

        if score is not None or error:
            by_evaluator[evaluator].append({
                'score': float(score) if score is not None else None,
                'error': error,
                'label': attrs.get('gen_ai.evaluation.score.label', 'N/A'),
                'explanation': attrs.get('gen_ai.evaluation.explanation', 'N/A'),
                'session_id': attrs.get('session.id', 'unknown'),
                'trace_id': record.get('traceId', '')
            })
    except (json.JSONDecodeError, TypeError) as e:
        # Do not swallow this. A parse failure here used to look like
        # 'no sessions need attention', which is indistinguishable from a
        # healthy agent.
        print(f'WARNING: could not parse a record ({e}). If you see this for every '
              f'record, /tmp/eval-results.jsonl is not one-JSON-per-line.',
              file=sys.stderr)
        continue

needs_attention = []
for evaluator, sessions in by_evaluator.items():
    is_pass_fail = all(s['score'] in (0.0, 1.0, None) for s in sessions) and 'trajectory' in evaluator.lower()
    if is_pass_fail:
        # PASS/FAIL evaluators (e.g. TrajectoryCompliance): every FAIL is needs-attention,
        # there's no gradient to sort by.
        flagged = [s for s in sessions if s['score'] == 0.0 or s['error']]
    else:
        # Graded content evaluators: sort ascending, take the lowest-scoring + errors.
        sessions.sort(key=lambda x: x['score'] if x['score'] is not None else -1)
        # Normalize the 'low' cutoff to the observed scale (1-5 vs 0.0-1.0)
        max_score = max((s['score'] for s in sessions if s['score'] is not None), default=1.0)
        cutoff = max_score * 0.8
        flagged = [s for s in sessions if s['score'] is None or s['score'] < cutoff][:10]
    for s in flagged:
        s['evaluator'] = evaluator
        needs_attention.append(s)

for s in needs_attention:
    print(json.dumps(s))
" > /tmp/low-scoring-sessions.jsonl

echo "Sessions needing attention (across all evaluators): $(wc -l < /tmp/low-scoring-sessions.jsonl)"
cat /tmp/low-scoring-sessions.jsonl | jq -r '"[\(.evaluator)] score=\(.score) session=\(.session_id)"'
:::

:::alert{type="info" header="Optional: what this looked like on a live account"}
Dogfooding with both evaluators deployed: content scores (`edd_workshop_travel_quality`) clustered at 4.0-5.0 out of 5 across every session, so nothing to triage there. The real signal was two `TrajectoryCompliance` sessions scoring `0.0`/`FAIL`, each missing `query_sites`/`plan_route`: genuine violations the content scores gave no hint of.
:::

## Step 4: Resolve the original query for each flagged session

The evaluation log event carries only `trace_id`, not the user's prompt. Where the prompt
text lives depends on which path you took, so the resolver below tries both:

| | Path B (OpenInference adapter) | Path A (Strands on Runtime) |
|---|---|---|
| Prompt text is in | the **root** span's `input.value`, the one with `openinference.span.kind: AGENT`, in `aws/spans` | the agent log record's `body.input.messages[]`, in `/aws/bedrock-agentcore/runtimes/$RUNTIME_LOG_SUFFIX` |
| Why | OpenInference puts I/O on the span | Strands spans carry `gen_ai.usage.*` and `gen_ai.request.model` but **no prompt text**; the record is where input and output live (it is what Module 1's check 2 asserts) |

On Path B the span kind is what you match on, not just the presence of `input.value`. `TOOL` spans
carry an `input.value` too, holding the tool's arguments, and they reach the log group before the
root span does, because the root span only closes when the run ends. Take the first
`input.value` you find and every case gets a prompt like
`{"attraction_name":"Royal Palace","meal_type":"dinner"}` instead of the question the user asked.

On Path A the message content is a JSON string nested inside the message, so it needs
one extra `json.loads`, which is what `_text_from_message` below handles.

:::code{language=bash showCopyAction=true showLineNumbers=false}
source /workshop/edd-workshop/config.env

python3.12 -c "
import json, os, subprocess

AGENT_LG = '/aws/bedrock-agentcore/runtimes/' + (
    os.environ.get('RUNTIME_LOG_SUFFIX') or os.environ.get('SERVICE_NAME', ''))


def events(log_group, trace_id):
    '''Every record mentioning this trace id, in one API call.'''
    out = subprocess.run(
        ['aws', 'logs', 'filter-log-events',
         '--log-group-name', log_group,
         '--filter-pattern', f'\"{trace_id}\"',
         '--max-items', '20', '--region', 'us-east-1',
         '--query', 'events[].message', '--output', 'json'],
        capture_output=True, text=True).stdout
    try:
        return [json.loads(m) for m in (json.loads(out) or [])]
    except Exception:
        return []


def _text_from_message(msg):
    '''Strands nests the text as a JSON string inside content.content.'''
    content = msg.get('content')
    inner = content.get('content') if isinstance(content, dict) else content
    if isinstance(inner, str):
        try:
            parts = json.loads(inner)
        except Exception:
            return inner
        if isinstance(parts, list):
            for p in parts:
                if isinstance(p, dict) and p.get('text'):
                    return p['text']
    return None


def resolve_query(trace_id):
    # Path B: the prompt is on the ROOT span, the one whose span kind is AGENT.
    # Match on the kind, do not just take the first input.value in the trace:
    # TOOL spans carry an input.value too (their arguments), and they are
    # exported before the root span, which only closes at the end of the run.
    for span in events('aws/spans', trace_id):
        attrs = span.get('attributes', {})
        if attrs.get('openinference.span.kind') == 'AGENT' and attrs.get('input.value'):
            return attrs['input.value']
    # Path A: Strands puts it in the agent log record instead.
    for rec in events(AGENT_LG, trace_id):
        body = rec.get('body')
        if not isinstance(body, dict) or not isinstance(body.get('input'), dict):
            continue
        for msg in body['input'].get('messages', []):
            if msg.get('role') == 'user':
                text = _text_from_message(msg)
                if text:
                    return text
    return 'N/A'


with open('/tmp/low-scoring-sessions.jsonl') as f:
    sessions = [json.loads(line) for line in f if line.strip()]

for s in sessions:
    trace_id = s.get('trace_id', '')
    s['query'] = resolve_query(trace_id) if trace_id else 'N/A'

with open('/tmp/low-scoring-sessions-with-query.jsonl', 'w') as f:
    for s in sessions:
        f.write(json.dumps(s) + '\n')

print(f'Resolved queries for {len(sessions)} sessions')
for s in sessions:
    print(f\"  [{s['evaluator']}] score={s['score']} query={s['query'][:70]}\")
"
:::

That is one or two `filter-log-events` calls per flagged session: fine for the bottom
10-20, not built for hundreds.

:::alert{type="warning" header="If every query comes back N/A"}
On Path A, check that `RUNTIME_LOG_SUFFIX` is set (`source config.env`, then
`echo $RUNTIME_LOG_SUFFIX`): with it empty the resolver looks in
`/aws/bedrock-agentcore/runtimes/` and finds nothing. Note also that a Logs Insights
`start-query` against `aws/spans` alone cannot fix this, because on Path A the prompt text
is not in the spans at all.
:::

## Step 5: Transform into Case objects

Convert the extracted sessions into the `Case` interface. This writes the script to
disk, which the next command runs:

:::code{language=bash showCopyAction=true showLineNumbers=false}
mkdir -p scripts
cat > scripts/generate-cases-from-production.ts <<'TS'
import { readFileSync } from 'fs';
// Import the real interface instead of redeclaring it, so a field rename in
// cases.ts shows up here as a type error rather than as cases that merge
// cleanly and then run with an undefined prompt.
import type { Case } from '../eval/cases.js';

interface LowScoringSession {
  score: number;
  query: string;
  explanation: string;
  session_id: string;
  evaluator: string;
  error?: string;
}

const sessions: LowScoringSession[] = readFileSync('/tmp/low-scoring-sessions-with-query.jsonl', 'utf-8')
  .split('\n')
  .filter(Boolean)
  .map(line => JSON.parse(line));

// One session can be flagged by BOTH evaluators (a trajectory FAIL usually drags
// the content score down too), so group by session before generating cases.
// Without this you get two identical cases for one production failure.
const bySession = new Map<string, LowScoringSession[]>();
for (const s of sessions.filter(s => s.query && s.query !== 'N/A')) {
  const key = s.session_id || s.query;
  bySession.set(key, [...(bySession.get(key) ?? []), s]);
}

const newCases: Case[] = [...bySession.values()].map((flags, i) => ({
  name: `production_regression_${i + 1}`,
  prompt: flags[0].query,
  // Conservative: expect at least query_sites to be called
  expected_trajectory: ['query_sites', 'plan_route'],
  trajectory_match: 'in_order' as const,
  // Every evaluator that flagged this session, so the rubric carries both lenses
  rubric: flags
    .map(f => f.error
      ? `Fix the evaluation error: ${f.error}`
      : `[${f.evaluator}] ${f.explanation}`)
    .join(' | '),
}));

console.log('// Generated from production low-scoring sessions');
console.log('// Review and adjust expected_trajectory and rubric before committing');
console.log(JSON.stringify(newCases, null, 2));
TS
:::

Run it:

:::code{language=bash showCopyAction=true showLineNumbers=false}
npx tsx scripts/generate-cases-from-production.ts
:::

Review the output, fix each case's `expected_trajectory` to match the path that is actually
correct, then merge into `eval/cases.ts` and **run the new case** to prove it is wired up:

:::code{language=bash showCopyAction=true showLineNumbers=false}
npm run eval -- --case production_regression_1
:::

Run it even though the merge looks obviously fine. `eval/` sits outside the `include` in
`tsconfig.json` and `tsx` transpiles without type-checking, so a case whose fields do not match
the `Case` interface will not fail `npm run build`: it will run with an undefined prompt and an
undefined rubric, and report a score for a question it never asked.

:::alert{type="warning" header="Read the judge's explanation before you paste it into a test case"}
The explanation is evidence, not a verdict, and it sometimes tells you about the
**evaluation** rather than the agent. A real one from this exercise:

> "The user's original query isn't shown (only the agent response is provided as both
> query context and response) ... Without tool output to compare against, I cannot
> confirm factual accuracy."

That content score was partly about what the judge could see. A `rubric` copied
from it verbatim would encode the evaluator's blind spot as a requirement on your agent.
Keep the part that describes a real gap in the answer, drop the part that describes the
judge's own missing context.
:::

## Step 6: Hand the same job to a coding agent

Everything above is mechanical, which is what a coding agent is for. Give it this prompt:

:::alert{type="info" header="First time driving Claude Code here: expect approval prompts"}
This is the first delegated task in the workshop, and Claude Code starts in **manual mode**: it
pauses for permission before each action, and every shell command asks separately from every file
edit. This task is mostly AWS CLI calls, so it will ask before the first one and then again as it
explores. **shift+tab** at the start switches to `accept edits on`, which silences the file-edit
prompts but not the shell ones.

If it looks stalled, it is almost always waiting on a prompt. Page 4.3 has the fuller version of
this note, including what the first-launch banner and the auto-update warning mean.
:::

> Query the AgentCore evaluation results log group for the lowest-scoring sessions and any evaluation errors. In healthy agent systems, scores cluster high (0.8-1.0), so focus on the bottom 10 sessions by score and any sessions with LogEventMissingException or other errors. For each session needing attention, extract the user query, the tool-call trajectory, and the judge's explanation. Transform these into new test cases matching the `Case` interface in `eval/cases.ts`. Focus on patterns we don't already cover in the existing cases.
>
> The user's prompt text is not in the same place on both paths. On **Path B** it is on the root span in `aws/spans`, the one whose `openinference.span.kind` is `AGENT`, in `input.value`. On **Path A** the Strands spans carry **no prompt text at all**: it lives in the agent log record's `body.input.messages[]` in `/aws/bedrock-agentcore/runtimes/$RUNTIME_LOG_SUFFIX`, as a JSON string nested inside the message content. Check which path this account is on before you start digging.

:::alert{type="warning" header="Tell it where the prompt text lives, or it will hunt the wrong log group"}
That second paragraph is not optional padding. Measured on a Path A account without it, the agent
went looking for `AGENT` spans with user input in `aws/spans`, found none (correctly, because Strands
does not put prompt text on spans), then oscillated between the spans and the runtime log group for
roughly ten approval rounds and never wrote a case. It is the same fact Step 4's table carries, and
the scripted path needs it for exactly the same reason.
:::

It will:

1. **Query** the evaluation log group using the AWS CLI
2. **Filter** for lowest-scoring sessions and evaluation errors
3. **Correlate** with X-Ray traces to extract the actual tool-call trajectory
4. **Compare** against existing cases to avoid duplicates
5. **Generate** new `Case` objects with appropriate `expected_trajectory` and `rubric`
6. **Write** the cases directly into `eval/cases.ts`

Your job is to review the generated cases and verify each `expected_trajectory`. The human provides judgment; the agent provides execution.

The scripted path teaches you the data flow, and it is the one to use where no coding agent is available. But nobody runs a six-step shell pipeline every week forever. Delegated, it runs on a schedule (weekly, or after any traffic shift) and ground truth stays fresh without anyone remembering to refresh it. Either way the discipline holds: never ship without both lenses green on the expanded case set.

**Next: [Apply the wire-up Power](../03-apply-wireup-power/).**
