#!/usr/bin/env bash
# Capture the two names AgentCore Runtime generates for your agent, and append
# them to config.env so every new terminal picks them up.
#
# Two names, because Runtime uses different forms in different places:
#   RUNTIME_LOG_SUFFIX    keeps the runtime id, hyphen-joined.  Used to build the
#                         CloudWatch log group name (Path A.3's CFN parameter).
#   RUNTIME_SERVICE_NAME  drops the runtime id, dot-joined.  This is the
#                         service.name stamped inside every record, and what
#                         Module 2's evaluator filters on.
#
# The emitted name is read from a real log record rather than derived by string
# manipulation, so it cannot drift from what Runtime actually writes.
#
# Usage:  ./scripts/capture-runtime-names.sh [log-group-suffix]
set -uo pipefail

# Resolve an interpreter once. The Code Editor ships python3.12; fall back to
# python3 so this still works on a box where it is named differently.
PY=""
for c in python3.12 python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then echo "ERROR: no python interpreter found on PATH" >&2; exit 1; fi

REGION="${AWS_REGION:-us-east-1}"
CONFIG="${CONFIG_ENV:-/workshop/edd-workshop/config.env}"
PREFIX="/aws/bedrock-agentcore/runtimes/"

die() { printf '\nERROR: %s\n' "$1" >&2; shift; for l in "$@"; do printf '  %s\n' "$l" >&2; done; exit 1; }

# ---------------------------------------------------------------- 1. log group
if [ "$#" -ge 1 ] && [ -n "${1:-}" ]; then
  LOG_SUFFIX="${1##*/runtimes/}"
else
  FOUND=()
  while IFS= read -r line; do
    [ -n "$line" ] && FOUND+=("$line")
  done < <(
    aws logs describe-log-groups --log-group-name-prefix "$PREFIX" \
      --region "$REGION" --query 'logGroups[].logGroupName' --output text 2>/dev/null \
      | tr '\t' '\n'
  )

  if [ "${#FOUND[@]}" -eq 0 ]; then
    die "No log group found under ${PREFIX}" \
        "Runtime creates it on the FIRST invocation, so this is expected if you" \
        "have not invoked the agent yet. Run:" \
        "" \
        "    agentcore invoke \"What is the Grand Museum?\"" \
        "" \
        "then re-run this script."
  fi

  if [ "${#FOUND[@]}" -gt 1 ]; then
    printf '\nERROR: found %d runtime log groups. Not guessing which is yours.\n' "${#FOUND[@]}" >&2
    printf '  %s\n' "${FOUND[@]}" >&2
    printf '\nRe-run with the one you just deployed, for example:\n  %s %s\n' \
      "$0" "${FOUND[0]##*/runtimes/}" >&2
    exit 1
  fi

  LOG_SUFFIX="${FOUND[0]##*/runtimes/}"
fi

LOG_GROUP="${PREFIX}${LOG_SUFFIX}"

# ------------------------------------------------- 2. emitted service.name
# Read it out of an actual record. Retry briefly: the log group can exist a few
# seconds before the sidecar's first export lands in it.
EMITTED=""
for attempt in 1 2 3 4 5 6; do
  EMITTED=$(
    aws logs filter-log-events --log-group-name "$LOG_GROUP" \
      --max-items 5 --region "$REGION" --output json 2>/dev/null \
    | "$PY" -c '
import json, sys
try:
    events = json.load(sys.stdin).get("events", [])
except Exception:
    sys.exit(0)
for e in events:
    try:
        rec = json.loads(e["message"])
    except Exception:
        continue
    name = rec.get("resource", {}).get("attributes", {}).get("service.name")
    if name:
        print(name)
        break
'
  )
  [ -n "$EMITTED" ] && break
  [ "$attempt" -lt 6 ] && { printf 'waiting for the first log record (%d/6)...\n' "$attempt"; sleep 10; }
done

if [ -z "$EMITTED" ]; then
  die "Log group ${LOG_GROUP} exists but carries no records yet." \
      "Invoke the agent once, wait ~15s, then re-run:" \
      "" \
      "    agentcore invoke \"What is the Grand Museum?\""
fi

# ------------------------------------------------------------- 3. persist
if [ ! -w "$(dirname "$CONFIG")" ] && [ ! -w "$CONFIG" ]; then
  die "Cannot write to $CONFIG"
fi
touch "$CONFIG"
# Idempotent: drop any previous values before appending the current ones.
sed -i '/^export RUNTIME_LOG_SUFFIX=/d;/^export RUNTIME_SERVICE_NAME=/d' "$CONFIG"
{
  printf 'export RUNTIME_LOG_SUFFIX=%s\n' "$LOG_SUFFIX"
  printf 'export RUNTIME_SERVICE_NAME=%s\n' "$EMITTED"
} >> "$CONFIG"

export RUNTIME_LOG_SUFFIX="$LOG_SUFFIX"
export RUNTIME_SERVICE_NAME="$EMITTED"

cat <<SUMMARY

Captured and saved to $CONFIG:

  RUNTIME_LOG_SUFFIX   = $LOG_SUFFIX
      -> log group ${LOG_GROUP}
      -> pass this to Path A.3 as the CFN ServiceName parameter

  RUNTIME_SERVICE_NAME = $EMITTED
      -> read from a real log record, not guessed
      -> Module 2's evaluator filters on this

Every new terminal now picks both up, because config.env is sourced on login.
In THIS shell, run:  source $CONFIG
SUMMARY
