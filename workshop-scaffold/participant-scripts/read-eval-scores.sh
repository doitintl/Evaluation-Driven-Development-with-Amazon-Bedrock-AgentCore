#!/usr/bin/env bash
# Read evaluation scores out of the AgentCore evaluation-results log group and
# print one line per score: evaluator, session, score, label, and the judge's
# explanation.
#
# Scores land ~15-25 minutes after a session goes idle, so an empty result soon
# after invoking is normal rather than broken.
#
# Usage:  ./scripts/read-eval-scores.sh [evaluator-filter] [max]
#   evaluator-filter  substring to match, e.g. TrajectoryCompliance. Default: all.
#   max               how many records to read, default 20
set -uo pipefail

# Resolve an interpreter once. The Code Editor ships python3.12; fall back to
# python3 so this still works on a box where it is named differently.
PY=""
for c in python3.12 python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then echo "ERROR: no python interpreter found on PATH" >&2; exit 1; fi

REGION="${AWS_REGION:-us-east-1}"
FILTER="${1:-}"
MAX="${2:-20}"

# Find the results log group. Ask the LIVE config where it writes, rather than
# guessing from log-group names.
#
# This matters because every change to EvaluatorMode / ServiceName creates a new
# config id, and therefore a new results log group, while the old ones stay
# behind. Picking by name prefix and taking the first match returned the OLDEST
# generation, so after Module 2.6 you were shown the previous evaluator's scores
# and would conclude the custom evaluator had worked. outputConfig is
# authoritative and needs no name matching.
EVAL_LG=""
CFG_ID=$(aws bedrock-agentcore-control list-online-evaluation-configs \
  --region "$REGION" \
  --query 'onlineEvaluationConfigs[0].onlineEvaluationConfigId' \
  --output text 2>/dev/null)
if [ -n "$CFG_ID" ] && [ "$CFG_ID" != "None" ]; then
  EVAL_LG=$(aws bedrock-agentcore-control get-online-evaluation-config \
    --region "$REGION" --online-evaluation-config-id "$CFG_ID" \
    --query 'outputConfig.cloudWatchConfig.logGroupName' \
    --output text 2>/dev/null)
  [ "$EVAL_LG" = "None" ] && EVAL_LG=""
fi

# Fallback: no readable config (for example the stack was deleted), so scan by name.
if [ -z "$EVAL_LG" ]; then
  EVAL_LG=$(aws logs describe-log-groups \
    --log-group-name-prefix /aws/bedrock-agentcore/evaluations/ \
    --region "$REGION" --query 'logGroups[].logGroupName' --output text 2>/dev/null \
    | tr '\t' '\n' | sed '/^$/d' | grep -i "edd" | tail -1)
fi

if [ -z "$EVAL_LG" ]; then
  EVAL_LG=$(aws logs describe-log-groups \
    --log-group-name-prefix /aws/bedrock-agentcore/evaluations/ \
    --region "$REGION" --query 'logGroups[0].logGroupName' --output text 2>/dev/null)
fi

if [ -z "$EVAL_LG" ] || [ "$EVAL_LG" = "None" ]; then
  cat >&2 <<'MSG'
ERROR: no evaluation-results log group exists yet.

The Online Evaluation config creates it when it writes its FIRST result, so this
means no session has been scored yet. Either the wait is not over (allow 15-25
minutes after the session goes idle), or no session was eligible. Run
./scripts/verify-telemetry.sh to confirm spans are actually being recorded.
MSG
  exit 1
fi

printf '\nReading %s\n' "$EVAL_LG"
[ -n "$FILTER" ] && printf 'Filtering for: %s\n' "$FILTER"
printf '\n'

# --max-items, not --limit: against these log groups the raw --limit API
# parameter can return zero events even when real scores exist.
if [ -n "$FILTER" ]; then
  RAW=$(aws logs filter-log-events --log-group-name "$EVAL_LG" \
          --filter-pattern "\"$FILTER\"" --max-items "$MAX" --region "$REGION" \
          --query 'events[].message' --output json 2>/dev/null)
else
  RAW=$(aws logs filter-log-events --log-group-name "$EVAL_LG" \
          --filter-pattern '"gen_ai.evaluation"' --max-items "$MAX" --region "$REGION" \
          --query 'events[].message' --output json 2>/dev/null)
fi

printf '%s' "$RAW" | "$PY" -c '
import json, sys, collections

try:
    msgs = json.load(sys.stdin) or []
except Exception:
    msgs = []

rows = []
for m in msgs:
    try:
        rec = json.loads(m)
    except Exception:
        continue
    a = rec.get("attributes", {}) or {}
    # Measured key first, legacy spelling only as a fallback, for BOTH fields.
    # Live records carry "gen_ai.evaluation.name" and "session.id"; the longer
    # "gen_ai.session.id" / "...evaluator_id" spellings are absent. Keeping the
    # measured key first means a record that somehow carried both would still
    # report the current value, which is what step 2.3 tells the participant.
    name = a.get("gen_ai.evaluation.name") or a.get("gen_ai.evaluation.evaluator_id") or "?"
    rows.append({
        "evaluator": name,
        "session": str(a.get("session.id") or a.get("gen_ai.session.id") or "?"),
        "score": a.get("gen_ai.evaluation.score.value", "-"),
        "label": a.get("gen_ai.evaluation.score.label", ""),
        "explanation": (a.get("gen_ai.evaluation.explanation") or "").strip(),
        "error": a.get("gen_ai.evaluation.error", ""),
    })

if not rows:
    print("  No scores yet.")
    print("  Scores appear 15-25 minutes after a session goes idle. Judge-queue load")
    print("  can push it past that, so nothing at 15 minutes does not mean failure.")
    raise SystemExit(1)

by_eval = collections.defaultdict(list)
for r in rows:
    by_eval[r["evaluator"]].append(r)

# Group by evaluator: scores from different evaluators are on different scales
# and must not be ranked against each other.
for evaluator, items in by_eval.items():
    print("  {} ({} score(s))".format(evaluator, len(items)))
    for r in items:
        line = "    session {:<22} score={:<6} {}".format(
            r["session"][:22], str(r["score"]), r["label"])
        print(line.rstrip())
        if r["error"]:
            print("      error: {}".format(r["error"][:160]))
        elif r["explanation"]:
            print("      {}".format(r["explanation"][:160]))
    print()

print("  {} score(s) across {} evaluator(s)".format(len(rows), len(by_eval)))
'
