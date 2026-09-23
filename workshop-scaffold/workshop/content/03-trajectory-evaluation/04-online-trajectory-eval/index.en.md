---
title: "3.4 Deploy trajectory evaluation to AgentCore"
weight: 40
---

**Scenario.** `npm run eval` only runs when a developer remembers to run it. You want every production session trajectory-checked automatically, the same way `Builtin.Helpfulness` already scores content, so you hear about skipped `query_sites` calls the moment they start.

AgentCore **Custom Code-Based Evaluators** are Lambda functions that receive session spans and return a verdict. That is how you deploy your `trajectory.ts` logic to production traffic.

:::alert{type="success" header="The one idea: the same matcher, now unattended"}
Your pre-deploy trajectory check becomes a post-deploy one without changing what it means. After this page, both lenses score every session automatically: content by a managed LLM judge, trajectory by your own code.
:::

## How it works

You already have one evaluator running. You are adding a second, of a different
kind, alongside it:

| | Module 2's evaluator | What you add here |
|---|---|---|
| **Evaluator** | `Builtin.Helpfulness`, a managed LLM judge | Custom Code-Based Evaluator, your own Lambda |
| **Reads** | the agent record's input and output text | `sessionSpans`, every span in the trace |
| **Asks** | "was the answer helpful?" | "did the agent call the right tools?" |
| **Returns** | a 0.0 to 1.0 score | PASS or FAIL |
| **Logic lives in** | a rubric and a model | your `trajectory.ts` matcher, as code |

Both run on every session, and both results land in the same evaluation log
group. Two lenses, automated, no human in the loop.

## Step 1: Write the Lambda function

The Lambda receives `sessionSpans`, the same span data you saw in X-Ray, and returns a verdict. This one implements the `superset` check: `query_sites`, `plan_route`, and `suggest_dining` must all appear, in any order, extras allowed.

:::code{language=bash showCopyAction=true showLineNumbers=false}
cd /workshop/edd-workshop
mkdir -p lambda/trajectory-evaluator
:::

:::code{language=bash showCopyAction=true showLineNumbers=false}
cat > lambda/trajectory-evaluator/index.py << 'EOF'
"""
Custom Code-Based Evaluator: Trajectory Compliance
Checks that the agent called all expected tools (superset mode).
"""

EXPECTED_TOOLS = ["query_sites", "plan_route", "suggest_dining"]


def handler(event, context):
    """
    Input: event with evaluationInput.sessionSpans
    Output: {label, value, explanation}
    """
    spans = event.get("evaluationInput", {}).get("sessionSpans", [])
    
    # Extract tool names from spans
    # Span names follow the pattern "execute_tool {tool_name}" (strands) 
    # or "tool: {tool_name}" (openinference)
    actual_tools = []
    for span in spans:
        name = span.get("name", "")
        if name.startswith("execute_tool "):
            actual_tools.append(name.replace("execute_tool ", ""))
        elif name.startswith("tool: "):
            actual_tools.append(name.replace("tool: ", ""))
    
    # Superset check: all expected tools must appear at least once
    missing = [t for t in EXPECTED_TOOLS if t not in actual_tools]
    
    if not missing:
        return {
            "label": "PASS",
            "value": 1.0,
            "explanation": (
                f"Trajectory compliant. Agent called all expected tools: "
                f"{', '.join(EXPECTED_TOOLS)}. "
                f"Actual sequence: {' → '.join(actual_tools)}"
            )
        }
    else:
        return {
            "label": "FAIL",
            "value": 0.0,
            "explanation": (
                f"Trajectory violation. Missing tools: {', '.join(missing)}. "
                f"Expected: {', '.join(EXPECTED_TOOLS)}. "
                f"Actual: {' → '.join(actual_tools) if actual_tools else '(no tools called)'}"
            )
        }
EOF
:::

:::alert{type="info" header="Plumbing: why a Lambda instead of an LLM-as-Judge"}
Trajectory matching is deterministic: "did tool X appear in the span list?" has exactly one right answer for a given set of spans. An LLM judge would burn tokens and add non-determinism on top of the variation the agent already has. This Lambda runs in ~50ms at near-zero cost. Save judge tokens for content quality, where judgment is genuinely needed.
:::

## Step 2: Deploy the Lambda

:::code{language=bash showCopyAction=true showLineNumbers=false}
cd /workshop/edd-workshop/lambda/trajectory-evaluator

# Package
zip trajectory-evaluator.zip index.py

# Create execution role
aws iam create-role \
  --role-name trajectory-evaluator-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }' \
  --region us-east-1

aws iam attach-role-policy \
  --role-name trajectory-evaluator-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Wait for role propagation
sleep 10

# Create Lambda function
aws lambda create-function \
  --function-name edd-trajectory-evaluator \
  --runtime python3.12 \
  --handler index.handler \
  --role arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/trajectory-evaluator-role \
  --zip-file fileb://trajectory-evaluator.zip \
  --timeout 60 \
  --region us-east-1
:::

Expected output, abridged (`create-function` prints the full configuration):
```json
{
    "FunctionName": "edd-trajectory-evaluator",
    "FunctionArn": "arn:aws:lambda:us-east-1:ACCOUNT:function:edd-trajectory-evaluator",
    "Runtime": "python3.12",
    "Handler": "index.handler",
    "State": "Pending",
    "StateReason": "The function is being created.",
    "StateReasonCode": "Creating"
}
```

`State: Pending` is correct here: `create-function` returns before the function
finishes provisioning. It flips to `Active` within a few seconds, and the next step
does not need it to be `Active` yet.

## Step 3: Register the evaluator in AgentCore

Register the Lambda as a `TRACE`-level code-based evaluator and save its id for the next step:

:::code{language=bash showCopyAction=true showLineNumbers=false}
LAMBDA_ARN=$(aws lambda get-function \
  --function-name edd-trajectory-evaluator \
  --query 'Configuration.FunctionArn' --output text \
  --region us-east-1)

cat > /tmp/traj_evaluator_config.json <<JSON
{
  "codeBased": {
    "lambdaConfig": {
      "lambdaArn": "$LAMBDA_ARN",
      "lambdaTimeoutInSeconds": 60
    }
  }
}
JSON

TRAJ_EVALUATOR_ID=$(aws bedrock-agentcore-control create-evaluator \
  --region us-east-1 \
  --evaluator-name TrajectoryCompliance \
  --level TRACE \
  --description 'Checks that the agent called query_sites, plan_route, and suggest_dining (superset mode).' \
  --evaluator-config file:///tmp/traj_evaluator_config.json \
  --query 'evaluatorId' --output text)

echo "$TRAJ_EVALUATOR_ID" > /tmp/traj_evaluator_id.txt
echo "Trajectory evaluator: $TRAJ_EVALUATOR_ID"
:::

Expected output, an id of the form:
```
Trajectory evaluator: TrajectoryCompliance-XXXXXXXXXX
```

:::alert{type="info" header="Plumbing: why the AWS CLI and not boto3"}
The Code Editor ships no `boto3` and no `pip` to install it, so every AgentCore call in this module goes through `aws bedrock-agentcore-control`. The `--evaluator-config` document uses the same member names as the API (`codeBased.lambdaConfig.lambdaArn`, `lambdaTimeoutInSeconds`), so it is a direct translation of the equivalent SDK call.
:::

## Step 4: Add the evaluator to your Online Evaluation Config

Your Module 2 config runs one content judge. Attach the trajectory evaluator **alongside**
it so both run on every session.

The evaluator list you send **replaces** the previous list, so the command below reads
what is already attached and appends to it. Do not hardcode a judge id: if you did the
optional page 2.6, the attached judge is your own custom rubric, not
`Builtin.Helpfulness`, and hardcoding would silently detach it.

:::code{language=bash showCopyAction=true showLineNumbers=false}
source /workshop/edd-workshop/config.env

TRAJ_EVALUATOR_ID=$(cat /tmp/traj_evaluator_id.txt)

EVAL_CFG_ID=$(aws bedrock-agentcore-control list-online-evaluation-configs \
  --region us-east-1 \
  --query 'onlineEvaluationConfigs[?contains(onlineEvaluationConfigName, `edd_workshop`)].onlineEvaluationConfigId | [0]' \
  --output text)

echo "Found evaluation config: $EVAL_CFG_ID"

# Whatever judge is attached today (Builtin.Helpfulness, or your 2.6 custom rubric)
EXISTING=$(aws bedrock-agentcore-control get-online-evaluation-config \
  --region us-east-1 \
  --online-evaluation-config-id "$EVAL_CFG_ID" \
  --query 'evaluators[].evaluatorId' --output text)

echo "Already attached: $EXISTING"

# Rebuild the list: everything that was there, plus the trajectory evaluator
EVAL_ARGS=""
for id in $EXISTING; do
  [ "$id" = "$TRAJ_EVALUATOR_ID" ] && continue   # keep it idempotent
  EVAL_ARGS="$EVAL_ARGS evaluatorId=$id"
done

aws bedrock-agentcore-control update-online-evaluation-config \
  --region us-east-1 \
  --online-evaluation-config-id "$EVAL_CFG_ID" \
  --evaluators $EVAL_ARGS evaluatorId="$TRAJ_EVALUATOR_ID"
:::

Confirm both evaluators are now attached:

:::code{language=bash showCopyAction=true showLineNumbers=false}
aws bedrock-agentcore-control get-online-evaluation-config \
  --region us-east-1 \
  --online-evaluation-config-id "$EVAL_CFG_ID" \
  --query 'evaluators[].evaluatorId' --output text
:::

Expected: your content judge alongside your `TrajectoryCompliance-XXXXXXXXXX` id, for
example

```
Builtin.Helpfulness    TrajectoryCompliance-JiOdJm8J7D
```

or, if you did page 2.6,

```
TrajectoryCompliance-JiOdJm8J7D    edd_workshop_travel_quality-UWzZhe44WU
```

:::alert{type="info" header="Plumbing: this is a partial update, your sampling and log-group config survive"}
Sending only `--evaluators` does **not** blank the rest of the config. Your `rule` (sampling rate and session timeout) and `dataSourceConfig.cloudWatchLogs` (log group plus `serviceNames`) survive untouched, and the config stays `ACTIVE`.

The evaluator list is the exception: it is replaced wholesale, which is why Step 4 reads
the current list first. If you only see `TrajectoryCompliance-...` in the output above,
your content judge got detached; re-run the block, which restores it from `$EXISTING`.
:::

:::alert{type="warning" header="If EVAL_CFG_ID prints None"}
No config name contained `edd_workshop`. List them all and pick yours (its name contains your `SERVICE_NAME`), then re-run the update with that id:

```bash
aws bedrock-agentcore-control list-online-evaluation-configs \
  --region us-east-1 \
  --query 'onlineEvaluationConfigs[].[onlineEvaluationConfigName,onlineEvaluationConfigId]' \
  --output table
```
:::

:::alert{type="warning" header="If the update fails with a Lambda permission ValidationException"}
AgentCore Online Eval assumes the eval-execution role (`<ProjectName>-eval-exec`, created by Module 2's `edd-eval-and-obs` stack) to call your code-based evaluator. Without permission you get:

```
ValidationException: The execution role provided for this Evaluation does not have
permission to access the specified Lambda functions ...
```

The workshop CFN stack grants this already **as long as you kept the default Lambda name** (`edd-trajectory-evaluator`): the role's `InvokeCodeBasedEvaluatorLambda` statement is scoped to `edd-trajectory-evaluator*` and `<ProjectName>-*`. If you renamed the Lambda, add the permission explicitly (`ProjectName` defaults to `edd-workshop`):

```bash
source /workshop/edd-workshop/config.env
EVAL_ROLE_NAME="edd-workshop-eval-exec"   # = <ProjectName>-eval-exec
aws iam put-role-policy \
  --role-name "$EVAL_ROLE_NAME" \
  --policy-name LambdaInvoke \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [{
      \"Effect\": \"Allow\",
      \"Action\": [\"lambda:InvokeFunction\", \"lambda:GetFunction\"],
      \"Resource\": \"$LAMBDA_ARN\"
    }]
  }"
# IAM changes take a few seconds to propagate; if the update below still
# fails with the permission error, wait ~15s and retry.
```
:::

## Step 5: Generate traffic and verify trajectory scores

Use the **instrumented** entrypoint for the path you took in Module 1. `npm start` from
`travel-agent/` is the local dev entrypoint: it emits no spans, so the evaluator would
never see the session.

**Path A (Strands on AgentCore Runtime):**

:::code{language=bash showCopyAction=true showLineNumbers=false}
cd /workshop/edd-workshop/travel-agent-strands
agentcore invoke "Plan a 2-day Luminara trip arriving Monday with a history focus."
:::

**Path B (any framework, via the OpenInference adapter):**

:::code{language=bash showCopyAction=true showLineNumbers=false}
cd /workshop/edd-workshop/openinference-aws-adapter
USER_QUERY="Plan a 2-day Luminara trip arriving Monday with a history focus." npm start
:::

Allow 20-25 minutes for the session idle timeout plus evaluation. Judge-queue load can push it past what the idle-timeout math suggests, so seeing nothing at 15 minutes does not mean it failed. Then read the scores:

:::code{language=bash showCopyAction=true showLineNumbers=false}
cd /workshop/edd-workshop
./scripts/read-eval-scores.sh
:::

Expected output, grouped by evaluator because the two scales are not comparable:
```
  TrajectoryCompliance (1 score(s))
    session abc123def4560a         score=1.0    PASS
      Trajectory compliant. Agent called all expected tools: query_sites, plan_route, suggest_dining.

  Builtin.Helpfulness (1 score(s))
    session abc123def4560a         score=0.83   Very Helpful
      The user requested a 2-day history-focused trip arriving Monday...

  2 score(s) across 2 evaluator(s)
```

If you did the optional page 2.6, the second group is your own rubric
(`edd_workshop_travel_quality`, on its 1-5 scale) instead of `Builtin.Helpfulness`.
Either way you should see two groups: one content score, one trajectory verdict.

Both evaluators ran on the same session. Two scores, two lenses, fully automated.

**Expected result, your custom evaluator scores a live session.** `TrajectoryCompliance` returns `PASS` (1.0) on a compliant session, with an explanation naming the tools it matched:

![Expected result: the custom TrajectoryCompliance evaluator scoring a live session PASS (1.0) in the evaluation-results log group, with an explanation listing the matched tools query_sites, plan_route, suggest_dining](/static/images/module-3/online-trajectory-pass.png)

:::alert{type="warning" header="If the result comes back empty"}
Only `Builtin.Helpfulness` appearing means the trajectory evaluator did not run:
re-check Step 4 attached **both** evaluator ids. Nothing at all means the wait is
not over yet.
:::

## Step 6: Prove the trajectory lens catches a failure

Send a query narrow enough that the agent has no reason to plan a route or look up
sites. Again, use the instrumented entrypoint.

**Path A (Strands on AgentCore Runtime):**

:::code{language=bash showCopyAction=true showLineNumbers=false}
cd /workshop/edd-workshop/travel-agent-strands
agentcore invoke "Suggest dinner near the Royal Palace"
:::

**Path B (any framework, via the OpenInference adapter):**

:::code{language=bash showCopyAction=true showLineNumbers=false}
cd /workshop/edd-workshop/openinference-aws-adapter
USER_QUERY="Suggest dinner near the Royal Palace" npm start
:::

On a dining-only query the agent typically calls just `suggest_dining`, which is fewer
tools than the global `superset` rule demands. Wait 20-25 minutes again and re-run the
Step 5 verification. Expect a FAIL:

```
  TrajectoryCompliance (4 score(s))
    session 7292da58-2b5d-40dc-91f  score=0.0    FAIL
      Trajectory violation. Missing tools: query_sites, plan_route.
      Expected: query_sites, plan_route, suggest_dining. Actual: suggest_dining
    session a1d63961-7129-4b33-817  score=1.0    PASS
      Trajectory compliant. Agent called all expected tools: query_sites,
      plan_route, suggest_dining. Actual sequence: query_sites → query_sites →
      plan_route → suggest_dining
```

Your earlier compliant sessions stay `PASS` in the same output, which is what makes the
contrast readable: one evaluator, one rule, two verdicts.

Check the content score on the same session. Both of these are valid outcomes:

- **Red/Green**: content still scores well (the dining answer reads as plausible on its own) and trajectory alone catches the skipped constraint check. Per Module 3.5's framework: investigate the trajectory issue specifically.
- **Red/Red**: content also drops, because without `query_sites` data the answer leans on invented details a careful judge flags. Both lenses agree: revert or fix before shipping. This is arguably the stronger demonstration, since it shows content quality is not a reliable substitute for trajectory checking even when it usually looks like one.

Report whichever you see; there is no fixed script here.

:::alert{type="info" header="Optional: should a dinner-only query really fail trajectory?"}
That depends on your business rules. The `subset` mode from step 3.1 argues the opposite: for a scoped dining-only request (the `luminara_dining_only_scoped` case), calling ONLY `suggest_dining` is correct, because the agent should not over-plan.

Which surfaces a real design decision: a production trajectory evaluator wants per-query expected trajectories (ground truth), not one global expectation. Module 4 shows how to pull production examples into ground-truth cases. The global `superset` check is a reasonable start because it catches the most dangerous failure mode, skipping `query_sites` on constraint-rich queries.
:::

## What you've built

| Before this step | After this step |
|-----------------|-----------------|
| Trajectory evaluation runs only when a developer runs `npm run eval` locally | Trajectory evaluation runs automatically on **every production session** |
| Content quality scored continuously (Builtin.Helpfulness) | Content quality + trajectory compliance both scored continuously |
| Trajectory failures caught only by the 6 pre-deploy test cases | Trajectory failures caught on the full distribution of production queries |

`npm run eval` stays your pre-deploy gate for specific cases. The online evaluator is the post-deploy safety net for queries you never anticipated.

:::alert{type="info" header="Optional: extending the evaluator for production"}
Your Lambda checks a fixed `EXPECTED_TOOLS` list. In production, consider:

1. **Per-query ground truth**: pass expected trajectories as `evaluationReferenceInputs` (see [AWS docs on ground truth](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-based-evaluators.html))
2. **Multiple modes**: `in_order` for constraint-rich queries, `subset` for scoped ones
3. **Tool-call frequency**: alert on thrashing (more than 5 `query_sites` calls suggests confusion)
4. **LLM-as-Judge hybrid**: an LLM-judge custom evaluator with the `{expected_tool_trajectory}` and `{actual_tool_trajectory}` placeholders, for nuanced scoring that tolerates minor deviations
:::

When ready: **[Module 3.5: Summary](../05-summary/)**.
