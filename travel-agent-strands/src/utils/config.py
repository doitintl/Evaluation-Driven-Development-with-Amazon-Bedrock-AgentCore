# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Application config — mirrors utils/config.ts."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Optional


@dataclass
class AppConfig:
    """Runtime configuration for the travel-agent.

    Attributes:
        model_id: Bedrock model id; defaults to ``us.anthropic.claude-sonnet-4-6``.
        aws_region: AWS region (must be set via env).
        aws_profile: Optional AWS profile name.
    """

    model_id: str
    aws_region: str
    aws_profile: Optional[str] = None


def load_config() -> AppConfig:
    """Load ``AppConfig`` from environment variables.

    Mirrors the TypeScript ``loadConfig``: ``AWS_REGION`` is required; the model
    id falls back to ``us.anthropic.claude-sonnet-4-6``.
    """
    aws_region = os.environ.get("AWS_REGION")
    if not aws_region:
        sys.stderr.write("ERROR: AWS_REGION environment variable is required.\n")
        sys.exit(1)

    return AppConfig(
        model_id=os.environ.get("MODEL_ID", "us.anthropic.claude-sonnet-4-6"),
        aws_region=aws_region,
        aws_profile=os.environ.get("AWS_PROFILE"),
    )
