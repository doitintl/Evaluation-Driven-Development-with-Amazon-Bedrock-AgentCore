#!/usr/bin/env bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# Package deployment artifacts for Workshop Studio.
#
# Repo layout (as of the travel-agent pivot):
#   /edd-workshop                            (repo root)
#     /travel-agent                          (Richard's TS pi-mono Coordinator)
#     /solutions/module-1/agentcore-trajectory-adapter   (TS adapter solution)
#     /workshop-scaffold                     (this directory)
#       /infrastructure/stacks               (CFN templates)
#       /infrastructure/custom-resource-lambdas
#       /workshop                            (WS-Studio content)
#         /scripts/package_for_workshop.sh   (this file)
#         /static                            (root CFN copy + images)
#         /assets                            (S3-uploaded artifacts; this script writes here)
#         /content                           (markdown)
#
# Produces:
#   workshop-scaffold/workshop/static/main-stack.yaml         — root CFN
#   workshop-scaffold/workshop/assets/templates/*.yaml        — nested CFN
#   workshop-scaffold/workshop/assets/lambdas/eval_provisioner.zip
#   workshop-scaffold/workshop/assets/repo/edd-workshop.zip   — source repo
#
# Usage:
#   bash workshop-scaffold/workshop/scripts/package_for_workshop.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSHOP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SCAFFOLD_DIR="$(cd "$WORKSHOP_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SCAFFOLD_DIR/.." && pwd)"
INFRA_DIR="$SCAFFOLD_DIR/infrastructure"
TRAVEL_AGENT_DIR="$REPO_ROOT/travel-agent"
STATIC_DIR="$WORKSHOP_DIR/static"
ASSETS_DIR="$WORKSHOP_DIR/assets"

echo "=== 0/4 Clean previous assets ==="
rm -rf "$ASSETS_DIR"
mkdir -p "$ASSETS_DIR/templates" "$ASSETS_DIR/repo" "$ASSETS_DIR/lambdas" \
         "$STATIC_DIR/images"

echo "=== 1/4 Copy CFN templates ==="
cp "$INFRA_DIR/stacks/main-stack.yaml" "$STATIC_DIR/main-stack.yaml"
# Templates shipped (all three are the whole deploy now — the optional EKS
# path and its ecr/eks/eks-app/cognito/spa stacks were retired):
#   - network-stack-default-vpc      (auto-deployed by main)
#   - code-editor-stack              (auto-deployed by main)
#   - agentcore-eval-and-obs         (participant-deployed in Modules 1-2)
for f in network-stack-default-vpc code-editor agentcore-observability agentcore-eval-and-obs; do
  src="$INFRA_DIR/stacks/${f}-stack.yaml"
  # Some files (e.g. network-stack-default-vpc.yaml,
  # agentcore-eval-and-obs.yaml) already include or omit the -stack suffix.
  if [ ! -f "$src" ]; then
    src="$INFRA_DIR/stacks/${f}.yaml"
  fi
  if [ ! -f "$src" ]; then
    echo "WARN: missing template for ${f}, skipping" >&2
    continue
  fi
  cp "$src" "$ASSETS_DIR/templates/$(basename "$src")"
done

# Stage the static/ tree (IAM policies, images) into assets/ so the S3
# `aws s3 sync assets/ … --delete` uploads it too. Workshop Studio resolves
# contentspec references like `static/iam/participant-write.json` from the
# assets bucket at deploy time — if it's missing the deploy fails pre-CFN with
# "error getting iam policy json from builder artifacts bucket ... 404".
# CRITICAL: the participantRole IAM policy lives here; without it every event
# deployment_fails before any CloudFormation stack is created.
STATIC_SRC="$WORKSHOP_DIR/static"
if [ -d "$STATIC_SRC/iam" ] || [ -d "$STATIC_SRC/images" ]; then
  mkdir -p "$ASSETS_DIR/static"
  cp -r "$STATIC_SRC/." "$ASSETS_DIR/static/"
  # main-stack.yaml is deployed as the ROOT stack from static/main-stack.yaml
  # by Workshop Studio; it doesn't need to also live under assets/static/.
  rm -f "$ASSETS_DIR/static/main-stack.yaml"
  echo "  → staged static/ (iam + images) into assets/static/"
fi

echo "=== 2/4 Package custom-resource Lambdas ==="
# eval_provisioner needs a recent boto3 (Lambda runtime ships boto3 ~1.34
# which lacks bedrock-agentcore-control evaluator + online-eval APIs).
EVAL_PROV_DIR="$INFRA_DIR/custom-resource-lambdas/eval_provisioner"
EVAL_BUILD="$ASSETS_DIR/lambdas/.eval_provisioner_build"
rm -rf "$EVAL_BUILD" && mkdir -p "$EVAL_BUILD"
cp "$EVAL_PROV_DIR/index.py" "$EVAL_BUILD/"
PIP="${PIP:-python3 -m pip}"
$PIP install --quiet --platform manylinux2014_x86_64 --target "$EVAL_BUILD" \
  --implementation cp --python-version 3.12 --only-binary=:all: \
  -r "$EVAL_PROV_DIR/requirements.txt"
(cd "$EVAL_BUILD" && zip -qr "$ASSETS_DIR/lambdas/eval_provisioner.zip" .)
rm -rf "$EVAL_BUILD"
echo "  → $ASSETS_DIR/lambdas/eval_provisioner.zip ($(du -h "$ASSETS_DIR/lambdas/eval_provisioner.zip" | cut -f1))"

# CloudFormation compares Code.S3Key, not object content, so replacing the zip
# at the same key never updates a deployed function. Publish a content-hashed
# copy as well: pass its key as ProvisionerCodeKey to force a code update when
# hot-patching an event that is already running.
EVAL_PROV_SHA=$(shasum -a 256 "$ASSETS_DIR/lambdas/eval_provisioner.zip" | cut -c1-8)
cp "$ASSETS_DIR/lambdas/eval_provisioner.zip" \
   "$ASSETS_DIR/lambdas/eval_provisioner-${EVAL_PROV_SHA}.zip"
echo "  → $ASSETS_DIR/lambdas/eval_provisioner-${EVAL_PROV_SHA}.zip (hashed copy;"
echo "    hot-patch with --parameter-overrides ProvisionerCodeKey=lambdas/eval_provisioner-${EVAL_PROV_SHA}.zip)"


echo "=== 3/4 Repo zip (downloaded into Code Editor) ==="
# Includes:
#   - travel-agent/                 pi-mono TS Coordinator (Path B + Modules 3-4)
#   - travel-agent-strands/         Strands Python Coordinator (Path A)
#   - solutions/                    canonical adapter solution (Path B)
#   - kiro-powers/                  Module 3 references these
#   - cfn/agentcore-eval-and-obs.yaml   deployed in Modules 1-2
#
# kiro-powers and the cfn/ folder are staged from the scaffold tree
# because they live outside the repo root proper. They get zipped INTO
# the archive at top level so the participant's working directory has
# `kiro-powers/` and `cfn/` siblings to `travel-agent/`.
REPO_ZIP="$ASSETS_DIR/repo/edd-workshop.zip"

# Stage kiro-powers
KIRO_SRC="$SCAFFOLD_DIR/kiro-powers"
KIRO_STAGE="$REPO_ROOT/.kiro-powers-staged-for-zip"
if [ -d "$KIRO_SRC" ]; then
  rm -rf "$KIRO_STAGE"
  cp -r "$KIRO_SRC" "$KIRO_STAGE"
fi

# Stage cfn/ folder with the participant-deployed CFN templates
# (Module 1 observability + Module 2 eval).
CFN_STAGE="$REPO_ROOT/.cfn-staged-for-zip"
rm -rf "$CFN_STAGE"
mkdir -p "$CFN_STAGE"
cp "$INFRA_DIR/stacks/agentcore-observability.yaml" "$CFN_STAGE/"
cp "$INFRA_DIR/stacks/agentcore-eval-and-obs.yaml" "$CFN_STAGE/"

# Stage scripts/ with the participant helper scripts (name capture, telemetry
# verify). These replace long inline heredocs in the content: the participant
# runs one named command and can open the file to read the assertions.
SCRIPTS_SRC="$SCAFFOLD_DIR/participant-scripts"
SCRIPTS_STAGE="$REPO_ROOT/.scripts-staged-for-zip"
rm -rf "$SCRIPTS_STAGE"
if [ -d "$SCRIPTS_SRC" ]; then
  cp -r "$SCRIPTS_SRC" "$SCRIPTS_STAGE"
  chmod +x "$SCRIPTS_STAGE"/*.sh
fi

(
  cd "$REPO_ROOT"
  # travel-agent and solutions are always present
  ZIP_TARGETS="travel-agent solutions"
  # travel-agent-strands is added by the strands-implementation pass
  if [ -d "travel-agent-strands" ]; then
    ZIP_TARGETS="$ZIP_TARGETS travel-agent-strands"
  fi
  if [ -d "$KIRO_STAGE" ]; then
    mv "$KIRO_STAGE" "kiro-powers"
    ZIP_TARGETS="$ZIP_TARGETS kiro-powers"
  fi
  if [ -d "$CFN_STAGE" ]; then
    mv "$CFN_STAGE" "cfn"
    ZIP_TARGETS="$ZIP_TARGETS cfn"
  fi
  if [ -d "$SCRIPTS_STAGE" ]; then
    mv "$SCRIPTS_STAGE" "scripts"
    ZIP_TARGETS="$ZIP_TARGETS scripts"
  fi
  # NB: exclude ALL dotenv variants (.env, .env.backup*, .env.baseline, .env.sim,
  # timestamped backups) — these are local dev state and have leaked a real IAM
  # role ARN (account id) into the shipped zip before. Keep ONLY *.env.example,
  # which are the intentional participant-facing templates. `zip -x` globs are
  # matched against the archive path, so re-add the examples after the broad
  # exclude via a second pass would drop them; instead we exclude the specific
  # non-example variants explicitly.
  #
  # travel-agent/results/ is excluded for the same class of reason: `npm run eval`
  # writes reports there, and three of the filenames Modules 3.2/3.3 tell the
  # participant to create (baseline_sonnet.md, candidate.md, after_prompt_fix.md)
  # would arrive pre-populated with a previous run's numbers. Those numbers
  # contradict the lesson (a shipped candidate.md showed nova-lite at 6/6, against
  # 3.2's central "the swap regressed" finding). .gitignore alone is not enough:
  # this script zips the working tree, so a local eval run would re-ship them.
  zip -r "$REPO_ZIP" $ZIP_TARGETS \
    -x "*.git/*" \
    -x "*node_modules/*" \
    -x "*dist/*" \
    -x "*.venv/*" \
    -x "*__pycache__/*" \
    -x "*.pyc" \
    -x "*.DS_Store" \
    -x "*.zip" \
    -x "*.tar.gz" \
    -x "*.env" \
    -x "*.env.backup" \
    -x "*.env.backup.*" \
    -x "*.env.baseline" \
    -x "*.env.sim" \
    -x "*.env.local" \
    -x "travel-agent/results/*" \
    -x "travel-agent/results" \
    > /dev/null
  # Clean up staged copies after zipping
  if [ -d "kiro-powers" ] && [ -f "kiro-powers/byo-agentcore-evaluation/POWER.md" ]; then
    rm -rf kiro-powers
  fi
  if [ -d "cfn" ] && [ -f "cfn/agentcore-observability.yaml" ]; then
    rm -rf cfn
  fi
  if [ -d "scripts" ] && [ -f "scripts/capture-runtime-names.sh" ]; then
    rm -rf scripts
  fi
)
echo "  → $REPO_ZIP ($(du -h "$REPO_ZIP" | cut -f1))"

echo "=== 4/4 Done ==="
echo "  $STATIC_DIR/main-stack.yaml"
echo "  $ASSETS_DIR/templates/"
echo "  $ASSETS_DIR/lambdas/eval_provisioner.zip"
echo "  $ASSETS_DIR/repo/edd-workshop.zip"
