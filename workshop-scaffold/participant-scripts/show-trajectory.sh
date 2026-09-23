#!/usr/bin/env bash
# Print your agent's trajectory as recorded in the aws/spans log group: one row
# per span, with kind, duration, model, and token counts, then a per-session
# summary of how many AGENT / LLM / TOOL spans it produced.
#
# This is the same data the GenAI Observability console shows, in a form you can
# diff and paste. Open this file to see the queries; there is nothing hidden.
#
# Usage:  ./scripts/show-trajectory.sh [service-name] [minutes]
#   service-name  defaults to RUNTIME_SERVICE_NAME (Path A) or SERVICE_NAME (Path B)
#   minutes       how far back to look, default 15
set -uo pipefail

# Resolve an interpreter once. The Code Editor ships python3.12; fall back to
# python3 so this still works on a box where it is named differently.
PY=""
for c in python3.12 python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then echo "ERROR: no python interpreter found on PATH" >&2; exit 1; fi

REGION="${AWS_REGION:-us-east-1}"
SVC="${1:-${RUNTIME_SERVICE_NAME:-${SERVICE_NAME:-}}}"
MINUTES="${2:-15}"

if [ -z "$SVC" ]; then
  cat >&2 <<'MSG'
ERROR: no service name available.

  Path A: run ./scripts/capture-runtime-names.sh, then `source config.env`
  Path B: `source /workshop/edd-workshop/config.env`
  Or pass one: ./scripts/show-trajectory.sh <service-name>
MSG
  exit 1
fi

START_MS=$(( ($(date +%s) - MINUTES * 60) * 1000 ))
printf '\nTrajectory for %s (last %s min)\n\n' "$SVC" "$MINUTES"

aws logs filter-log-events \
  --log-group-name aws/spans \
  --filter-pattern "\"$SVC\"" \
  --start-time "$START_MS" \
  --max-items 200 --region "$REGION" --output json 2>/dev/null \
| "$PY" -c '
import json, sys, collections

try:
    data = json.load(sys.stdin)
except Exception:
    data = {}

rows = []
sessions = collections.defaultdict(collections.Counter)
for e in data.get("events", []):
    try:
        s = json.loads(e["message"])
    except Exception:
        continue
    a = s.get("attributes", {}) or {}
    kind = a.get("openinference.span.kind") or ""
    sid = a.get("session.id") or s.get("traceId", "?")
    if kind:
        sessions[sid][kind] += 1
    rows.append((
        s.get("startTimeUnixNano", 0),
        s.get("name", "?"),
        kind or "-",
        (s.get("durationNano", 0) or 0) / 1e9,
        a.get("llm.model_name", "-"),
        a.get("llm.token_count.prompt", "-"),
        a.get("llm.token_count.completion", "-"),
    ))

if not rows:
    print("  No spans found.")
    print("  If you just ran the agent, wait ~30s and retry: the exporter batches.")
    print("  If it stays empty, run ./scripts/verify-telemetry.sh to find out why.")
    raise SystemExit(1)

rows.sort(key=lambda r: r[0])
print("  {:<34} {:<5} {:>7}  {:<30} {}".format("span", "kind", "sec", "model", "tokens in/out"))
print("  " + "-" * 92)
for _, name, kind, dur, model, tp, tc in rows:
    print("  {:<34} {:<5} {:>7.2f}  {:<30} {}/{}".format(
        str(name)[:34], kind[:5], dur, str(model)[:30], tp, tc))

print()
print("  {} spans across {} session(s)".format(len(rows), len(sessions) or 1))
for sid, c in sessions.items():
    print("    session {}: AGENT={} LLM={} TOOL={}".format(
        str(sid)[:20], c["AGENT"], c["LLM"], c["TOOL"]))
'
