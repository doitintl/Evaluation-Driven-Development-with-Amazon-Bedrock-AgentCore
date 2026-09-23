"""AgentCore Runtime entry-point for variant 1a.

Wraps the Coordinator agent in a ``BedrockAgentCoreApp`` so the AgentCore CLI
(``agentcore deploy`` / ``agentcore invoke``) can host it as an HTTP endpoint
with automatic OTEL instrumentation.

Reference:
https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-get-started.html
"""

from __future__ import annotations

import os
import sys

# Make ``src`` importable when this module runs from inside ``runtime/``.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from bedrock_agentcore.runtime import BedrockAgentCoreApp  # noqa: E402

from src.coordinator import create_coordinator_agent, null_callback_handler  # noqa: E402
from src.utils.config import load_config  # noqa: E402


app = BedrockAgentCoreApp()

# Build the Coordinator once at module load — the runtime keeps the process
# warm across invocations and reuses this agent.
_config = load_config()
_agent = create_coordinator_agent(_config, callback_handler=null_callback_handler)


@app.entrypoint
def invoke(payload: dict) -> str:
    """Handle a single agent invocation from AgentCore Runtime.

    The HTTP runtime delivers a JSON payload that has at least a ``prompt``
    field. The handler returns the agent's text response.
    """
    user_input = payload.get("prompt", "")
    if not user_input:
        return (
            "Missing 'prompt' in payload. Send a JSON body like "
            '{"prompt": "Plan a 2-day trip"}.'
        )

    result = _agent(user_input)

    # Strands AgentResult exposes ``message`` with content blocks.
    message = getattr(result, "message", None)
    if isinstance(message, dict):
        for block in message.get("content", []) or []:
            if isinstance(block, dict) and block.get("text"):
                return block["text"]
    return str(result)


if __name__ == "__main__":
    app.run()
