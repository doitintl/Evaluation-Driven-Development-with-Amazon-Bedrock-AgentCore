#!/usr/bin/env bash
# Deploy the workshop Code Editor (plus its own VPC and public subnet) into your
# own AWS account, without Workshop Studio.
#
# What it does:
#   1. Creates (or reuses) an S3 bucket for the workshop assets.
#   2. Zips the repo as <prefix>repo/<RepoName>.zip and uploads the CFN templates
#      to <prefix>templates/, which is where the Code Editor UserData expects them.
#   3. Deploys code-editor-stack.yaml (creates VPC 10.91.0.0/16 + 1 public subnet
#      unless EXISTING_VPC_ID / EXISTING_SUBNET_ID are set).
#   4. Prints the Code Editor URL.
#
# Usage:
#   ./deploy-own-account.sh [deploy|destroy]
#
# Optional env vars:
#   AWS_REGION (default us-east-1), STACK_NAME, BUCKET, PREFIX, REPO_NAME,
#   EXISTING_VPC_ID, EXISTING_SUBNET_ID, INSTANCE_TYPE
set -euo pipefail

ACTION="${1:-deploy}"
REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="${STACK_NAME:-edd-code-editor}"
PREFIX="${PREFIX:-edd/}"
REPO_NAME="${REPO_NAME:-edd-workshop}"
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.large}"
EXISTING_VPC_ID="${EXISTING_VPC_ID:-}"
EXISTING_SUBNET_ID="${EXISTING_SUBNET_ID:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCAFFOLD_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SCAFFOLD_DIR/.." && pwd)"
STACKS_DIR="$SCRIPT_DIR/stacks"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="${BUCKET:-edd-workshop-assets-${ACCOUNT_ID}-${REGION}}"

# The UserData concatenates ${ArtifactsPrefix} directly, so it must end in "/" (or be empty).
if [[ -n "$PREFIX" && "$PREFIX" != */ ]]; then PREFIX="${PREFIX}/"; fi

if [[ "$ACTION" == "destroy" ]]; then
  echo "Deleting stack $STACK_NAME in $REGION ..."
  aws cloudformation delete-stack --stack-name "$STACK_NAME" --region "$REGION"
  aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME" --region "$REGION"
  echo "Stack deleted. Bucket s3://$BUCKET was left in place; remove it with:"
  echo "  aws s3 rb s3://$BUCKET --force"
  echo "Resources from Modules 1-3 (edd-eval-and-obs, evaluators, ...) are NOT in this stack;"
  echo "see workshop/content/summary/index.en.md for their cleanup."
  exit 0
fi

echo "Account: $ACCOUNT_ID  Region: $REGION  Bucket: s3://$BUCKET/$PREFIX"

# 1. Bucket
if ! aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  echo "Creating bucket $BUCKET ..."
  if [[ "$REGION" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION"
  else
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" \
      --create-bucket-configuration "LocationConstraint=$REGION"
  fi
  aws s3api put-public-access-block --bucket "$BUCKET" \
    --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
  aws s3api put-bucket-encryption --bucket "$BUCKET" \
    --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
fi

# 2. Repo zip. Contents land in /workshop/<REPO_NAME>/, so the zip root is the repo root.
#    participant-scripts/ is shipped as scripts/ (the UserData chmods that dir).
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
STAGE="$WORK/stage"
mkdir -p "$STAGE"
rsync -a \
  --exclude '.git' --exclude 'node_modules' --exclude '.venv' --exclude '__pycache__' \
  --exclude 'cdk.out' --exclude '.env' --exclude 'workshop-scaffold/' \
  "$REPO_ROOT/" "$STAGE/"
mkdir -p "$STAGE/kiro-powers"
rsync -a "$SCAFFOLD_DIR/kiro-powers/" "$STAGE/kiro-powers/"
mkdir -p "$STAGE/scripts"
cp "$SCAFFOLD_DIR"/participant-scripts/*.sh "$STAGE/scripts/"
chmod +x "$STAGE"/scripts/*.sh
(cd "$STAGE" && zip -qr "$WORK/$REPO_NAME.zip" .)

echo "Uploading repo zip and templates ..."
aws s3 cp "$WORK/$REPO_NAME.zip" "s3://$BUCKET/${PREFIX}repo/$REPO_NAME.zip" --region "$REGION"
for tpl in code-editor-stack agentcore-observability agentcore-eval-and-obs; do
  aws s3 cp "$STACKS_DIR/$tpl.yaml" "s3://$BUCKET/${PREFIX}templates/$tpl.yaml" --region "$REGION"
done
# Module 2 eval stack loads <prefix>lambdas/eval_provisioner.zip. It needs a newer boto3 than
# the Lambda runtime ships, so bundle it (python3.12 / x86_64 manylinux wheels).
LAMBDA_SRC="$SCRIPT_DIR/custom-resource-lambdas/eval_provisioner"
PKG="$WORK/provisioner"
mkdir -p "$PKG"
python3 -m pip install -q -r "$LAMBDA_SRC/requirements.txt" -t "$PKG" \
  --platform manylinux2014_x86_64 --only-binary=:all: --python-version 3.12 --implementation cp
cp "$LAMBDA_SRC/index.py" "$PKG/"
(cd "$PKG" && zip -qr "$WORK/eval_provisioner.zip" .)
aws s3 cp "$WORK/eval_provisioner.zip" "s3://$BUCKET/${PREFIX}lambdas/eval_provisioner.zip" --region "$REGION"

# 3. Deploy
PARAMS=(
  "ProjectName=edd-workshop"
  "ArtifactsBucket=$BUCKET"
  "ArtifactsPrefix=$PREFIX"
  "InstanceType=$INSTANCE_TYPE"
  "RepoName=$REPO_NAME"
)
[[ -n "$EXISTING_VPC_ID" ]] && PARAMS+=("ExistingVpcId=$EXISTING_VPC_ID")
[[ -n "$EXISTING_SUBNET_ID" ]] && PARAMS+=("ExistingSubnetId=$EXISTING_SUBNET_ID")

aws cloudformation deploy \
  --region "$REGION" \
  --stack-name "$STACK_NAME" \
  --template-file "$STACKS_DIR/code-editor-stack.yaml" \
  --s3-bucket "$BUCKET" \
  --s3-prefix "${PREFIX}cfn-package" \
  --capabilities CAPABILITY_NAMED_IAM CAPABILITY_IAM \
  --parameter-overrides "${PARAMS[@]}"

# 4. Output
URL="$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='CodeEditorUrl'].OutputValue" --output text)"
echo
echo "Code Editor URL: $URL"
echo "(Give the instance a few minutes after CREATE_COMPLETE: UserData is still installing tools.)"
