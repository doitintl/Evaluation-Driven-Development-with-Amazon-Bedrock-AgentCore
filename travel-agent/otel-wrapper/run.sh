#!/usr/bin/env bash
# Run the OTEL-instrumented travel agent.
# Usage: ./run.sh "Plan a 2-day trip to Luminara"

set -euo pipefail
cd "$(dirname "$0")"

# Load .env BEFORE opentelemetry-instrument so ADOT's aws_configurator activates
set -a
source .env
set +a

exec .venv/bin/opentelemetry-instrument .venv/bin/python run_agent.py "$@"
