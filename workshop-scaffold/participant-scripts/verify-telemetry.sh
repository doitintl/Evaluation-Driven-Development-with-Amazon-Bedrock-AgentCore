#!/usr/bin/env bash
# Check that your agent's telemetry is complete and evaluation-ready.
#
# Three checks, in the order that matters:
#   1. Transaction Search is enabled and ACTIVE.
#   2. Agent log records, when your path emits them (Path A does, Path B does not).
#   3. Spans for your service are present in aws/spans.
#
# Open this file if you want to see the assertions. Nothing here is magic: it is
# the same AWS CLI calls you would run by hand, plus the checks that are easy to
# forget.
#
# Usage:  ./scripts/verify-telemetry.sh [service-name]
#   Path A: run with no argument after ./scripts/capture-runtime-names.sh
#   Path B: run with no argument; SERVICE_NAME comes from config.env
set -uo pipefail

# Resolve an interpreter once. The Code Editor ships python3.12; fall back to
# python3 so this still works on a box where it is named differently.
PY=""
for c in python3.12 python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then echo "ERROR: no python interpreter found on PATH" >&2; exit 1; fi

REGION="${AWS_REGION:-us-east-1}"
PASS=0; FAIL=0; NOTE_EMPTY=0
ok()   { printf '  [ok]   %s\n' "$1"; PASS=$((PASS+1)); }
bad()  { printf '  [FAIL] %s\n' "$1"; FAIL=$((FAIL+1)); }
info() { printf '         %s\n' "$1"; }

# Path A sets RUNTIME_SERVICE_NAME (emitted, dot-joined). Path B uses the fixed
# SERVICE_NAME from config.env. An explicit argument wins over both.
SVC="${1:-${RUNTIME_SERVICE_NAME:-${SERVICE_NAME:-}}}"
if [ -z "$SVC" ]; then
  cat >&2 <<'MSG'
ERROR: no service name available.

  Path A: run ./scripts/capture-runtime-names.sh first, then `source config.env`
  Path B: `source /workshop/edd-workshop/config.env`
  Or pass one explicitly: ./scripts/verify-telemetry.sh <service-name>
MSG
  exit 1
fi

# Path A's log group keeps the runtime id, so it is not derivable from SVC.
#
# An explicit argument must win outright. Otherwise, once Path A has written
# RUNTIME_LOG_SUFFIX into config.env, checking Path B with
#   ./scripts/verify-telemetry.sh travel-agent-edd-workshop
# would compare Path A's log group against Path B's service name and report a
# mismatch that is not real.
if [ "$#" -ge 1 ] && [ -n "${1:-}" ]; then
  LOG_SUFFIX="$SVC"
else
  LOG_SUFFIX="${RUNTIME_LOG_SUFFIX:-$SVC}"
fi
AGENT_LG="/aws/bedrock-agentcore/runtimes/${LOG_SUFFIX}"

printf '\nVerifying telemetry for service.name = %s\n\n' "$SVC"

# ------------------------------------------------ 1. is ingestion actually live
printf '1. Transaction Search\n'
DEST=$(aws xray get-trace-segment-destination --region "$REGION" \
        --query 'Destination' --output text 2>/dev/null)
STATUS=$(aws xray get-trace-segment-destination --region "$REGION" \
        --query 'Status' --output text 2>/dev/null)

if [ "$DEST" = "CloudWatchLogs" ] && [ "$STATUS" = "ACTIVE" ]; then
  ok "destination=CloudWatchLogs status=ACTIVE"
else
  bad "destination=${DEST:-unknown} status=${STATUS:-unknown}"
  info "Expected CloudWatchLogs/ACTIVE. Deploy the observability stack first;"
  info "it takes 6 to 10 minutes to settle. PENDING here is normal, not broken."
fi

# ---------------------------------------------------- 2. agent record shape
printf '\n2. Agent log group (%s)\n' "$AGENT_LG"
EVENTS_JSON=$(aws logs filter-log-events --log-group-name "$AGENT_LG" \
                --max-items 10 --region "$REGION" --output json 2>/dev/null)

if [ -z "$EVENTS_JSON" ]; then
  # A MISSING group means the same thing for Path B as an empty one (the
  # NO_EVENTS branch below): the adapter exports spans and never writes log
  # records, so nothing ever creates this group. On a both-paths account the
  # group only exists for whichever service name the observability stack was
  # deployed with, so the Path B name legitimately has none. Treat it the same
  # way: note it, and let check 3 decide. Flagging FAIL here reported a failure
  # on a Path B setup that was demonstrably healthy (16 spans present).
  NOTE_EMPTY=1
  info "log group not found"
  info "Runtime creates it on first invocation (Path A); Path B's stack creates it."
  info "For Path B a missing group is also correct: the adapter exports spans only,"
  info "so check 3 is your evidence."
else
  SHAPE=$(printf '%s' "$EVENTS_JSON" | "$PY" -c '
import json, sys
try:
    events = json.load(sys.stdin).get("events", [])
except Exception:
    events = []
if not events:
    print("NO_EVENTS"); raise SystemExit
target = None
for e in events:
    try:
        rec = json.loads(e["message"])
    except Exception:
        continue
    body = rec.get("body")
    if isinstance(body, dict) and ("input" in body or "output" in body):
        target = rec
        break
if target is None:
    print("NO_AGENT_RECORD"); raise SystemExit
body = target.get("body", {})
svc = target.get("resource", {}).get("attributes", {}).get("service.name", "")
scope = target.get("scope", {}).get("name", "")
has_input = "input" in body
has_output = "output" in body
correlation = "traceId" if target.get("traceId") else "none"
print("OK")
print("service.name=" + svc)
print("scope=" + scope)
print("has_input=" + str(has_input))
print("has_output=" + str(has_output))
print("correlation=" + correlation)
')
  case "$(printf '%s' "$SHAPE" | head -1)" in
    OK)
      ok "records present with input/output body"
      REC_SVC=$(printf '%s' "$SHAPE" | sed -n 's/^service.name=//p')
      info "$(printf '%s' "$SHAPE" | sed -n 's/^scope=/scope: /p')"
      info "correlation key: $(printf '%s' "$SHAPE" | sed -n 's/^correlation=//p')"
      if [ "$REC_SVC" = "$SVC" ]; then
        ok "record service.name matches ($REC_SVC)"
      else
        bad "record service.name is '$REC_SVC' but you are using '$SVC'"
        info "Module 2 filters on the value INSIDE the record. Use '$REC_SVC'."
      fi
      ;;
    NO_EVENTS)
      # Path B is span-only: its adapter exports traces and never writes log
      # records, so an empty log group here is the correct shape, not a failure.
      # Only treat it as a problem if no spans turned up either (check 3).
      NOTE_EMPTY=1
      info "no log records in this group"
      info "For Path B that is correct: the adapter exports spans only, so check 3"
      info "is your evidence. For Path A, invoke the agent and wait ~15s."
      ;;
    NO_AGENT_RECORD) bad "records exist but none carry an input/output body yet" ;;
    *)              bad "could not parse records" ;;
  esac
fi

# --------------------------------------------------------- 3. spans landed
printf '\n3. Spans in aws/spans\n'
# Look at RECENT spans only, and sample generously. Without --start-time,
# filter-log-events returns the OLDEST events in the group and --max-items
# truncates to those, so on an account with history this check would report
# the same earliest spans forever and never show a newly added tool.
SPAN_WINDOW_SECONDS=${SPAN_WINDOW_SECONDS:-3600}
SPAN_START=$(( ($(date +%s) - SPAN_WINDOW_SECONDS) * 1000 ))
SPAN_COUNT=$(aws logs filter-log-events --log-group-name aws/spans \
               --filter-pattern "\"$SVC\"" --start-time "$SPAN_START" \
               --max-items 200 --region "$REGION" \
               --output json 2>/dev/null \
             | "$PY" -c 'import json,sys
try: print(len(json.load(sys.stdin).get("events", [])))
except Exception: print(0)')

if [ "${SPAN_COUNT:-0}" -gt 0 ]; then
  ok "$SPAN_COUNT span record(s) found for $SVC in the last $((SPAN_WINDOW_SECONDS / 60)) min"
  aws logs filter-log-events --log-group-name aws/spans \
    --filter-pattern "\"$SVC\"" --start-time "$SPAN_START" \
    --max-items 200 --region "$REGION" \
    --query 'events[].message' --output json 2>/dev/null \
  | "$PY" -c '
import json, sys, collections
try:
    msgs = json.load(sys.stdin) or []
except Exception:
    msgs = []
c = collections.Counter()
for m in msgs:
    try:
        c[json.loads(m).get("name", "?")] += 1
    except Exception:
        pass
for name, n in c.most_common(12):
    print(f"         {n}x {name}")
'
else
  bad "no spans in aws/spans for $SVC"
  info "Spans emitted before Transaction Search was ready are rejected and lost"
  info "for good. If check 1 now reads ACTIVE, invoke the agent again, wait ~30s,"
  info "and re-run this script."
  # AgentCore can instead deliver spans to a `spans` stream inside the agent's
  # own log group (unified destination). The workshop pins that off, but say so
  # rather than reporting a bare failure if it turns out to be on.
  UNIFIED=$(aws logs describe-log-streams --log-group-name "$AGENT_LG" \
              --log-stream-name-prefix spans --region "$REGION" \
              --query 'logStreams[0].lastEventTimestamp' --output text 2>/dev/null)
  if [ -n "$UNIFIED" ] && [ "$UNIFIED" != "None" ]; then
    info ""
    info "NOTE: this agent is using the UNIFIED span destination: spans are in"
    info "  ${AGENT_LG}, stream 'spans'"
    info "rather than aws/spans. Set UNIFIED_TRACES_DESTINATION_ENABLED=false on"
    info "the runtime to match what the workshop's later steps query."
  fi
fi

printf '\n%d passed, %d failed\n' "$PASS" "$FAIL"
if [ "$NOTE_EMPTY" -eq 1 ] && [ "${SPAN_COUNT:-0}" -gt 0 ]; then
  printf '\nSpans are present and the agent log group is empty or absent. That is the\n'
  printf 'normal Path B shape: evaluation reads your spans. Nothing to fix.\n'
fi
[ "$FAIL" -eq 0 ] || exit 1
