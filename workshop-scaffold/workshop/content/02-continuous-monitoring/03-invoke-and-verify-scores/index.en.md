---
title: "2.3 Generate traffic and verify scores"
weight: 30
---

**Scenario.** The evaluator is deployed but has never seen a session, so it has
nothing to score. This step creates real traffic and then reads the scores back.
This is also where the workshop stops being about plumbing: **from here on you are
reading judgements about your agent's quality, not checking that wiring works.**

## Generate traffic

Invoke your agent 3 times to create sessions the evaluator can score. Use whichever invocation method matches the path you took in Module 1.

:::alert{type="warning" header="First confirm Transaction Search is ACTIVE"}
Sessions created while the trace destination is still `PENDING` are never indexed, so they can never be scored and the wait below will never end.

```bash
aws xray get-trace-segment-destination --region us-east-1 --query 'Status' --output text
```

Proceed only when this prints `ACTIVE`.
:::

### Path B: any framework (this workshop's pi-mono OpenInference adapter)

Run the same OpenInference adapter you built in Path B. It emits the trajectory spans the evaluator scores directly: nothing extra to enable:

```bash
cd /workshop/edd-workshop/openinference-aws-adapter
USER_QUERY="What attractions are open on weekends in Luminara?" npm start
USER_QUERY="Plan a 2-day trip focused on history, arriving Monday"   npm start
USER_QUERY="Suggest a dinner restaurant near the Royal Palace"       npm start
```

➡️ **For your framework:** invoke your instrumented agent however you normally run it: the point is only that each invocation emits OpenInference spans under `/aws/bedrock-agentcore/runtimes/${SERVICE_NAME}`.

### Path A: Strands on AgentCore Runtime

```bash
cd /workshop/edd-workshop/travel-agent-strands
agentcore invoke "What attractions are open on weekends in Luminara?"
agentcore invoke "Plan a 2-day trip focused on history, arriving Monday"
agentcore invoke "Suggest a dinner restaurant near the Royal Palace"
```

## Wait for scores

After the last invocation, the evaluation pipeline needs time:

1. **Session-idle timeout** (5 minutes): AgentCore waits for the session to go idle.
2. **Judge scoring** (~5-10 minutes): The LLM judge reads the transcript and scores it.

**Total wait: allow up to 20-25 minutes.** In practice this often lands in the 10-15 minute
range, but judge-queue load can push it well past that: if nothing has appeared by 15
minutes, that's not necessarily broken. Keep polling every few minutes rather than assuming
failure; only start troubleshooting (see below) if you're past 25 minutes with nothing.

:::alert{type="info" header="While you wait"}
Use this time productively:

- Re-read the architecture diagram from step 2.1 to solidify the mental model.
- Explore X-Ray traces from Module 1 in the CloudWatch console: **CloudWatch > X-Ray traces > Traces**.
- Browse the agent's log group to see the raw spans your agent emitted.
- Read ahead to step 2.4 (Explore the dashboard) so you know what to look for when scores arrive.
:::

## Verify scores arrived

After the wait, check the evaluation log group for scores:

```bash
cd /workshop/edd-workshop
./scripts/read-eval-scores.sh
```

:::alert{type="warning" header="Getting an empty result even after waiting?"}
The script says so explicitly rather than printing nothing. If it still reports no
scores after 25 minutes, work through the troubleshooting steps below.

If you write your own query against these log groups, use `--max-items` and not
`--limit`: the raw `--limit` API parameter can silently return zero events even
when real scores exist. The script uses `--max-items` for that reason.
:::

## Expected output

You should see JSON records containing:

- `gen_ai.evaluation.score.value`: a float between 0.0 and 1.0
- `gen_ai.evaluation.score.label`: the wording the console shows, for example `Above And Beyond`
- `gen_ai.evaluation.explanation`: the judge's reasoning for the score
- `gen_ai.evaluation.name`: which evaluator produced the score, here `Builtin.Helpfulness`
- `session.id`: matching the session IDs from your invocations

Example, abbreviated from a real record:

```json
{
  "gen_ai.evaluation.name": "Builtin.Helpfulness",
  "gen_ai.evaluation.score.value": 1.0,
  "gen_ai.evaluation.score.label": "Above And Beyond",
  "gen_ai.evaluation.explanation": "The user requested a 1-day trip starting Friday focusing on culture. The assistant's response delivers a comprehensive, well-organized itinerary that ...",
  "session.id": "bd8734a9-5221-42de-bfd0-ff8719f5e45e",
  "gen_ai.response.id": "6a86c659232c43303a2a72f8295d34b8"
}
```

:::alert{type="warning" header="Writing your own query? Two key names are not what you would guess"}
The record calls the session `session.id`, **not** `gen_ai.session.id`, and calls the evaluator
`gen_ai.evaluation.name`, **not** `gen_ai.evaluation.evaluator_id`. Measured on a live record: a grep
for either of those longer spellings returns nothing at all.

`read-eval-scores.sh` reads `gen_ai.evaluation.name` with a fallback to `evaluator_id`, and
`session.id` with a fallback to `gen_ai.session.id`, so the script keeps working whichever spelling the
service emits. A hand-written query on the wrong key returns zero rows and no error, which looks
exactly like "no scores yet".
:::

:::alert{type="info" header="More records than the three sessions you just sent?"}
Expected, and worth understanding. The evaluator scores every session in the agent's log group that
completes after the config goes `ACTIVE`, and Module 1's invocations live in that same log group.
Measured on a live account that moved straight from Module 1 to here: Module 1's three sessions were
scored about 13 minutes after they ran, this page's three about 15 minutes after, and
`read-eval-scores.sh` then reported **6 score(s) across 1 evaluator(s)**, not 3.

Sessions that finished well before the config existed are never picked up at all, so an account that
took a long break between the modules sees only the three from this page. Either count is correct;
match on ids rather than on the total.
:::

**Expected result, real scores in the console.** In the CloudWatch console, the evaluation-results log group shows one `gen_ai.evaluation.result` record per scored session. Each carries a `Builtin.Helpfulness` score and the judge's explanation, here, all three sessions scored 1.0 ("Above And Beyond"):

![The evaluation-results log group. Box 1: one gen_ai.evaluation.result record per scored session, each carrying a Builtin.Helpfulness score and the judge explanation](/static/images/module-2/eval-scores-expected.png)

Expand any record to read the judge's full free-text explanation, this is what makes the score actionable rather than just a number:

![Expected result: a score record expanded, showing the LLM judge's full explanation for why it scored the session as it did](/static/images/module-2/eval-score-explanation-expanded.png)

If you see per-session scores with explanations like these, your Online Evaluator is working end-to-end.

**Now interpret one record: don't just confirm it exists.** Pick any score record and answer these three questions (they're the difference between having telemetry and using it):

1. **Trace the causality:** find the `session.id` in the record, then find the same session id in your terminal output from the invocations above. That link, *your* CLI invocation → session → judge score, is the entire online-eval pipeline in one pair of ids. Work through the records until you find one you *can* match: some may belong to your Module 1 runs rather than to the three you just sent (the box above explains why). A record you cannot tie to any run of your own is the one telling you the score isn't measuring what you think it is.
2. **Audit the explanation against the transcript:** does the judge's explanation cite things the agent actually said? The judge is a measurement instrument, and instruments need calibration: reading a handful of explanations against the raw responses is how practitioners validate a judge before trusting its numbers. If the explanation is generic ("the response was helpful and detailed"), it's scoring *style*; if it cites specifics ("correctly excluded the Old Quarter Walking Tour for Sunday"), it's scoring *substance*.
3. **Ask what a LOW score would have looked like:** these Grand-Museum queries score high because the agent has the right data and prompt. What kind of user query would this judge score at 0.3, and would the *explanation* give you enough to reproduce the failure? Keep your answer in mind: Module 4 mines exactly those low-scoring sessions to build new test cases.

:::alert{type="info" header="Why 'Above And Beyond' everywhere is expected here, and what it would mean in production"}
All your sessions scoring 1.0 is correct for this controlled setup: you sent easy, well-supported queries to a healthy agent. In production, a wall of perfect scores is a signal to check the judge, not to celebrate: either traffic is easier than your users' real needs or the evaluator is too lenient. A useful online evaluator shows a distribution with a low tail; the tail is where the engineering work lives (and where Module 4 goes hunting).
:::

## Troubleshooting

If no scores appear after 25 minutes:

1. **Check the agent log group has events**: the evaluator cannot score sessions that were never logged:
   ```bash
   aws logs filter-log-events \
     --log-group-name "/aws/bedrock-agentcore/runtimes/${SERVICE_NAME}" \
     --max-items 3 \
     --query 'events[*].message' --output text | head -50
   ```

2. **Check the Online Evaluation Config status**: it must be `ACTIVE`:
   ```bash
   aws bedrock-agentcore-control list-online-evaluation-configs \
     --query 'onlineEvaluationConfigs[*].{name:onlineEvaluationConfigName, status:status}' \
     --output table
   ```
   (This subcommand needs a recent **AWS CLI v2**: see the version note in Module 0 setup if it reports `Invalid choice`.)

3. **Check the `serviceNames` filter matches what your records actually carry.** A mismatch means the evaluator watches the right log group but matches zero records inside it, so no error appears and nothing is ever scored:
   ```bash
   # what the config filters on
   CFG_ID=$(aws bedrock-agentcore-control list-online-evaluation-configs \
     --region us-east-1 \
     --query 'onlineEvaluationConfigs[0].onlineEvaluationConfigId' --output text)

   aws bedrock-agentcore-control get-online-evaluation-config \
     --online-evaluation-config-id "$CFG_ID" --region us-east-1 \
     --query 'dataSourceConfig.cloudWatchLogs.[logGroupNames,serviceNames]' --output json
   ```
   The `serviceNames` value must equal the emitted value **exactly**. On Path A these are two different strings (the log group keeps the runtime id, the emitted name is dot-joined), which is why Path A passes both `ServiceName` and `EmittedServiceName` in step 2.2.
