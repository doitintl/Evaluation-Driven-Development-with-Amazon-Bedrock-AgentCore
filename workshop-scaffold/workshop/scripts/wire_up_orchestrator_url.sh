#!/usr/bin/env bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# Discovers the ALB hostname from the EksApp deployment, then updates the SPA
# + Cognito + Code Editor sub-stacks with the real URL.
#
# Run this AFTER deploy_to_test_account.sh succeeds.
set -euo pipefail
STACK_NAME="${STACK_NAME:-edd-workshop}"
AWS_REGION="${AWS_REGION:-us-east-1}"
TEST_BUCKET="${TEST_BUCKET:?set TEST_BUCKET}"
TEST_PREFIX="${TEST_PREFIX:?set TEST_PREFIX}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

CLUSTER=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
  --region "$AWS_REGION" --query "Stacks[0].Outputs[?OutputKey=='EksClusterName'].OutputValue" --output text)
NS=edd-workshop

aws eks update-kubeconfig --name "$CLUSTER" --region "$AWS_REGION"

ALB=""
for i in $(seq 1 30); do
  ALB=$(kubectl -n "$NS" get ingress orchestrator-ingress \
    -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || true)
  [ -n "$ALB" ] && { echo "ALB: $ALB"; break; }
  echo "  waiting for ALB hostname... ($i/30)"
  sleep 15
done
[ -z "$ALB" ] && { echo "ALB not yet provisioned"; exit 1; }

ORCH_URL="http://${ALB}"
SPA_URL=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
  --region "$AWS_REGION" --query "Stacks[0].Outputs[?OutputKey=='SpaUrl'].OutputValue" --output text)

echo "=== Updating root stack with OrchestratorUrl=$ORCH_URL and CognitoCallback=$SPA_URL ==="
# A surgical CFN-update: pass through ArtifactsBucket/Prefix unchanged.
aws cloudformation update-stack --stack-name "$STACK_NAME" \
  --region "$AWS_REGION" \
  --use-previous-template \
  --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
  --parameters \
    ParameterKey=ArtifactsBucket,UsePreviousValue=true \
    ParameterKey=ArtifactsPrefix,UsePreviousValue=true \
    ParameterKey=ProjectName,UsePreviousValue=true \
    ParameterKey=ImageTag,UsePreviousValue=true \
    ParameterKey=JudgeModelId,UsePreviousValue=true || true

aws cloudformation wait stack-update-complete --stack-name "$STACK_NAME" --region "$AWS_REGION" || true

echo "Done. Open the SPA at: $SPA_URL"
