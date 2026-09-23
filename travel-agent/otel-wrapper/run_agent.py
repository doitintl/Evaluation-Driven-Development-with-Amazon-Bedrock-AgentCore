# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""run_agent.py - Main entry point for the OTEL-instrumented travel agent.

Run via opentelemetry-instrument to activate ADOT:
    cd travel-agent/otel-wrapper
    AWS_PROFILE=ml-sandbox AWS_REGION=us-east-1 \
      .venv/bin/opentelemetry-instrument .venv/bin/python run_agent.py "Plan a 2-day trip"

ADOT's aws_configurator handles SigV4 signing and exports spans+logs to CloudWatch
via the OTLP endpoint. The OTEL_EXPORTER_OTLP_LOGS_HEADERS env var routes log events
to the correct agent log group.
"""

import os
import subprocess
import sys
import time
import uuid

from dotenv import load_dotenv
from opentelemetry import baggage, trace
from opentelemetry.context import attach
from opentelemetry.trace import StatusCode

# 1. Load .env FIRST
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# 1.5 Manually initialize LoggerProvider with AWS OTLP exporter if not already set
# This is needed because ADOT's aws_configurator only initializes logs when
# OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true, which can cause hangs.
from opentelemetry._logs import get_logger_provider, set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk.resources import Resource
from botocore.session import Session as BotocoreSession

_lp = get_logger_provider()
if type(_lp).__name__ == 'ProxyLoggerProvider':
    # LoggerProvider not yet initialized - set it up with AWS SigV4 auth
    from amazon.opentelemetry.distro.exporter.otlp.aws.logs.otlp_aws_log_record_exporter import OTLPAwsLogRecordExporter
    from amazon.opentelemetry.distro.exporter.otlp.aws.logs._aws_cw_otlp_batch_log_record_processor import AwsCloudWatchOtlpBatchLogRecordProcessor

    # Parse service.name from OTEL_RESOURCE_ATTRIBUTES
    resource_attrs = os.environ.get("OTEL_RESOURCE_ATTRIBUTES", "")
    service_name = "travel-agent"
    if "service.name=" in resource_attrs:
        service_name = resource_attrs.split("service.name=")[1].split(",")[0]

    resource = Resource.create({
        "service.name": service_name,
        "aws.service.type": "gen_ai_agent",
    })

    logger_provider = LoggerProvider(resource=resource)

    # Parse log group/stream from headers
    headers_str = os.environ.get("OTEL_EXPORTER_OTLP_LOGS_HEADERS", "")
    log_group = None
    log_stream = None
    for h in headers_str.split(","):
        if "=" in h:
            k, v = h.split("=", 1)
            if k == "x-aws-log-group":
                log_group = v
            elif k == "x-aws-log-stream":
                log_stream = v

    aws_region = os.environ.get("AWS_REGION", "us-east-1")
    botocore_session = BotocoreSession()

    log_exporter = OTLPAwsLogRecordExporter(
        aws_region=aws_region,
        session=botocore_session,
        log_group=log_group,
        log_stream=log_stream,
        endpoint=os.environ.get("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", f"https://logs.{aws_region}.amazonaws.com/v1/logs"),
    )

    # Ensure log stream exists (OTLP endpoint requires it)
    import boto3
    logs_client = boto3.client('logs', region_name=aws_region)
    try:
        logs_client.create_log_stream(logGroupName=log_group, logStreamName=log_stream)
    except logs_client.exceptions.ResourceAlreadyExistsException:
        pass  # Stream already exists
    except Exception as e:
        print(f"Warning: Could not create log stream: {e}")

    logger_provider.add_log_record_processor(AwsCloudWatchOtlpBatchLogRecordProcessor(exporter=log_exporter))
    set_logger_provider(logger_provider)
    print(f"Initialized LoggerProvider with AWS SigV4 auth (log_group={log_group}, log_stream={log_stream})")

from invoke_agent_log_emitter import InvokeAgentLogEmitter

# 2. Set up session.id via OTEL baggage (BEFORE any spans are created)
session_id = os.environ.get("SESSION_ID", str(uuid.uuid4()))
ctx = baggage.set_baggage("session.id", session_id)
attach(ctx)

print(f"Session ID: {session_id}")

# 3. Get the TracerProvider and add InvokeAgentLogEmitter
provider = trace.get_tracer_provider()
real_provider = getattr(provider, "_real_provider", provider)
if hasattr(real_provider, "add_span_processor"):
    real_provider.add_span_processor(InvokeAgentLogEmitter())

# 4. Create a tracer with the required scope name
tracer = real_provider.get_tracer("strands.telemetry.tracer")

# 5. Create the invoke_agent span and invoke the agent subprocess
agent_name = os.environ.get("AGENT_NAME", "travel-agent-edd-workshop")
user_query = sys.argv[1] if len(sys.argv) > 1 else "Plan a 2-day trip"

# Store user query for the InvokeAgentLogEmitter to pick up
os.environ["_BYO_USER_QUERY"] = user_query

with tracer.start_as_current_span(f"invoke_agent {agent_name}") as span:
    span.set_attribute("gen_ai.agent.name", agent_name)
    span.set_attribute("gen_ai.operation.name", "invoke_agent")
    span.set_attribute("session.id", session_id)

    # 6. Invoke the TypeScript agent via subprocess
    start_time = time.time()

    result = subprocess.run(
        ["npx", "tsx", "src/main.ts", user_query],
        capture_output=True,
        text=True,
        cwd=os.path.join(os.path.dirname(__file__), ".."),
        env={**os.environ},
    )

    duration_ms = int((time.time() - start_time) * 1000)
    agent_response = result.stdout.strip()

    # 7. Set span attributes for the emitter to pick up
    span.set_attribute("_byo.user_query", user_query)
    span.set_attribute("_byo.agent_response", agent_response)
    span.set_attribute("gen_ai.agent.invocation.duration_ms", duration_ms)

    # 8. Print the response
    if agent_response:
        print(f"\n{agent_response}")

    # 9. Handle errors
    if result.returncode != 0:
        span.set_status(StatusCode.ERROR, "Agent subprocess failed")
        span.set_attribute("error.message", result.stderr.strip())
        print(f"\n[ERROR] Agent exited with code {result.returncode}", file=sys.stderr)
        if result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)

# 10. Flush providers to ensure log records are exported before exit.
# When ADOT's logger SDK initialization fails (or the agent process errors
# before the SDK is ready), `get_logger_provider()` returns a
# ProxyLoggerProvider that lacks `force_flush`. Guard against that so we
# don't crash on the way out.
from opentelemetry._logs import get_logger_provider as _get_lp
_lp = _get_lp()
if hasattr(_lp, "force_flush"):
    _lp.force_flush(timeout_millis=30000)
if hasattr(real_provider, "force_flush"):
    real_provider.force_flush(timeout_millis=10000)

if result.returncode != 0:
    sys.exit(result.returncode)
