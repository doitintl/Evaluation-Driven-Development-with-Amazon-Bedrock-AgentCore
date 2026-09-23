# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""InvokeAgentLogEmitter - Custom SpanProcessor for AgentCore Online Evaluator.

Watches for the `invoke_agent` span to end, then emits a log record with
the user query and agent response in the asymmetric format that AgentCore's
Online Evaluator expects.

The log record is emitted through the OTEL logging pipeline, so ADOT handles
the CloudWatch export (SigV4 signing, ADOT-native format transformation).
"""

import json
import os
import time

from opentelemetry import context as context_api, trace
from opentelemetry._logs import get_logger_provider, SeverityNumber
from opentelemetry.sdk.trace import SpanProcessor, ReadableSpan
from opentelemetry.trace import NonRecordingSpan, TraceFlags

STRANDS_SCOPE = "strands.telemetry.tracer"


class InvokeAgentLogEmitter(SpanProcessor):
    """SpanProcessor that emits log records when invoke_agent spans complete."""

    def on_start(self, span, parent_context=None):
        pass

    def on_end(self, span: ReadableSpan):
        if "invoke_agent" not in (span.name or ""):
            return

        attributes = dict(span.attributes) if span.attributes else {}

        user_query = attributes.get("_byo.user_query") or os.environ.get("_BYO_USER_QUERY", "")
        agent_response = attributes.get("_byo.agent_response", "")
        session_id = attributes.get("session.id", "default")

        if not user_query or not agent_response:
            return

        body = {
            "input": {
                "messages": [
                    {
                        "content": {"content": json.dumps([{"text": user_query}])},
                        "role": "user",
                    }
                ]
            },
            "output": {
                "messages": [
                    {
                        "content": {
                            "message": str(agent_response)[:10000],
                            "finish_reason": "end_turn",
                        },
                        "role": "assistant",
                    }
                ]
            },
        }

        logger_provider = get_logger_provider()
        # ADOT may return AwsLogsLoggerProvider or ProxyLoggerProvider
        # Check for get_logger method instead of strict type check
        if not hasattr(logger_provider, 'get_logger'):
            return

        otel_logger = logger_provider.get_logger(STRANDS_SCOPE, version="")

        span_ctx = trace.SpanContext(
            trace_id=span.context.trace_id,
            span_id=span.context.span_id,
            is_remote=False,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )
        ctx = trace.set_span_in_context(NonRecordingSpan(span_ctx))

        otel_logger.emit(
            timestamp=span.end_time,
            observed_timestamp=int(time.time_ns()),
            context=ctx,
            severity_number=SeverityNumber.INFO,
            severity_text="",
            body=body,
            attributes={
                "event.name": STRANDS_SCOPE,
                "session.id": session_id,
            },
        )

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis=None):
        return True
