#!/usr/bin/env bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# Deploy the workshop stack to YOUR AWS account for end-to-end testing.
# Mirrors what Workshop Studio does for participants but uses your own
# bucket prefix.
#
# Steps:
#   1. Run package_for_workshop.sh
#   2. Sync workshop/assets/ to your test bucket
#   3. Upload static/main-stack.yaml to S3 (CFN nested needs HTTPS URLs)
#   4. cloudformation deploy
#   5. (post-deploy) Run wire_up_orchestrator_url.sh to update Spa+Cognito with
#      the now-known ALB hostname.
#
# Required env: TEST_BUCKET, TEST_PREFIX (with trailing /), AWS_REGION

set -euo pipefail
TEST_BUCKET="${TEST_BUCKET:?set TEST_BUCKET (your test S3 bucket)}"
TEST_PREFIX="${TEST_PREFIX:?set TEST_PREFIX e.g. 'edd-workshop-dev/'}"
AWS_REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="${STACK_NAME:-edd-workshop}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "=== Package ==="
bash "$PROJECT_ROOT/workshop/scripts/package_for_workshop.sh"

echo "=== Sync assets ==="
aws s3 sync "$PROJECT_ROOT/workshop/assets/" "s3://${TEST_BUCKET}/${TEST_PREFIX}" \
  --region "$AWS_REGION" --delete

echo "=== Upload root template ==="
aws s3 cp "$PROJECT_ROOT/workshop/static/main-stack.yaml" \
  "s3://${TEST_BUCKET}/${TEST_PREFIX}main-stack.yaml" --region "$AWS_REGION"

echo "=== Deploy ==="
aws cloudformation deploy \
  --stack-name "$STACK_NAME" \
  --template-file "$PROJECT_ROOT/workshop/static/main-stack.yaml" \
  --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
  --parameter-overrides \
    ArtifactsBucket="$TEST_BUCKET" \
    ArtifactsPrefix="$TEST_PREFIX" \
  --region "$AWS_REGION" \
  --no-fail-on-empty-changeset

echo "=== Outputs ==="
aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$AWS_REGION" \
  --query 'Stacks[0].Outputs' --output table
