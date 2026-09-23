# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""CLI entry-point for the Strands Luminara travel-agent.

Modes:
- Single-shot: ``python main.py "Plan a 2-day trip"`` prints the agent reply
  to stdout and exits.
- Interactive (REPL): ``python main.py`` opens a readline-backed prompt loop.

This mirrors the pi-mono TypeScript ``src/main.ts``.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from typing import Optional

try:
    import readline  # noqa: F401  # imported for side-effect: line editing in REPL
except ImportError:  # pragma: no cover - Windows fallback
    pass

from src.coordinator import create_coordinator_agent, null_callback_handler
from src.utils.config import load_config


HELPFUL_MESSAGE = """I'm the Luminara Travel Planner! I can help you plan trips to our fictional city.

Try something like:
  • "Plan a 2-day trip focusing on history and food, arriving Monday"
  • "What attractions are open on weekends?"
  • "Suggest a day itinerary with the museum and botanical gardens"
"""


def _is_empty_or_nonsensical(prompt: str) -> bool:
    return len(prompt.strip()) < 3


def _is_credential_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return any(
        token in msg
        for token in (
            "credential",
            "unauthorizedexception",
            "expiredtoken",
            "expired token",
            "invalid identity token",
            "security token",
            "accessdenied",
        )
    )


def _extract_text(result: object) -> str:
    """Best-effort extraction of the agent's text response."""
    if result is None:
        return ""
    # Strands'AgentResult exposes ``message`` with a list of content blocks.
    message = getattr(result, "message", None)
    if isinstance(message, dict):
        content = message.get("content") or []
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("text")
        ]
        joined = "".join(parts).strip()
        if joined:
            return joined
    # Fallback: stringify
    return str(result).strip()


def run_single_shot(agent, prompt: str) -> int:
    if _is_empty_or_nonsensical(prompt):
        print(HELPFUL_MESSAGE)
        return 0

    try:
        result = agent(prompt)
        text = _extract_text(result)
        if not text:
            print(
                "Error: Agent produced no text response. Ensure your AWS "
                "credentials are valid and the model is accessible.",
                file=sys.stderr,
            )
            return 1
        print(text)
        return 0
    except Exception as exc:  # noqa: BLE001
        if _is_credential_error(exc):
            print(
                "Error: AWS credentials are invalid or expired. Please check "
                "your AWS_PROFILE and credentials configuration.",
                file=sys.stderr,
            )
            return 1
        print(f"Error: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1


def run_interactive(agent) -> int:
    print("Welcome to the Luminara Travel Planner!")
    print(
        "Plan your trip to the fictional city of Luminara. "
        "Ask about attractions, routes, and dining."
    )
    print('Type "exit" or "quit" to end the session.\n')

    while True:
        try:
            user_input = input("You> ")
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye! Happy travels!")
            return 0

        trimmed = user_input.strip()
        if trimmed.lower() in ("exit", "quit"):
            print("\nGoodbye! Happy travels!")
            return 0
        if not trimmed:
            continue

        try:
            result = agent(trimmed)
            text = _extract_text(result)
            print(f"\nAgent> {text}\n")
        except Exception as exc:  # noqa: BLE001
            if _is_credential_error(exc):
                print(
                    "\nError: AWS credentials are invalid or expired. Please "
                    "check your AWS_PROFILE and credentials configuration.\n",
                    file=sys.stderr,
                )
            else:
                print(f"\nError: {exc}\n", file=sys.stderr)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="travel-agent-strands",
        description="Luminara travel planner (Strands port). "
        "Run with no args for interactive REPL; pass a prompt for single-shot mode.",
    )
    parser.add_argument(
        "prompt",
        nargs="*",
        help="Optional prompt for single-shot mode. If omitted, REPL starts.",
    )
    args = parser.parse_args(argv)

    config = load_config()
    if args.prompt:
        # Single-shot mode silences streaming so we print the final reply once.
        agent = create_coordinator_agent(
            config, callback_handler=null_callback_handler
        )
        return run_single_shot(agent, " ".join(args.prompt))
    # Interactive mode keeps the default streaming callback so users see
    # tokens as the model emits them.
    agent = create_coordinator_agent(config)
    return run_interactive(agent)


if __name__ == "__main__":
    raise SystemExit(main())
