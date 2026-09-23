# Deploy notes — code-editor-stack.yaml (rationale moved out of UserData)

The EC2 `UserData` in `code-editor-stack.yaml` is capped at **16,384 bytes (base64)** by
EC2. To stay under it, verbose rationale that used to live as inline comments in the
`Fn::Base64: !Sub |` block was moved here. The executable logic is unchanged.

## External-binary verification (UserData installs)
Every externally-downloaded binary is cryptographically verified before execution — no
`curl | bash` pipe-to-bash anywhere:
- **AWS CLI v2** — detached PGP signature, verified against the AWS CLI team's public key
  (fingerprint `FB5D B77F D5C1 18B8 0511 ADA8 A631 0ACC 4672 475C`). The key is embedded
  inline so verification is self-contained.
- **kubectl 1.31.2 / Helm 3.16.4 / uv 0.11.32** — upstream SHA-256 checksums.
- **Code Editor `install.sh`** — AWS-internal artifact with **no** public PGP/SHA sidecar.
  Fetched over TLS from the official `code-editor.amazonaws.com` endpoint, downloaded to a
  file (not piped), its SHA-256 logged for audit, and trust-on-first-use **pinned** against a
  known-good value. A mismatch is a loud `SECURITY-AUDIT` warning (not a hard fail), since AWS
  may legitimately rotate it. Update `CODE_EDITOR_INSTALL_SHA256` when that happens.
- **`gnupg2`** is installed with `--allowerasing` (unconditionally) to replace the preinstalled
  `gnupg2-minimal`, which lacks the `gpg-agent` that `gpg --verify` needs.

## Claude Code (the workshop's only in-editor AI assistant)
Amazon Q / Q Developer / the AWS Toolkit are **deliberately not installed** anywhere on the box.
Claude Code is installed as both the CLI (`npm i -g @anthropic-ai/claude-code`) and the
`Anthropic.claude-code` editor extension (from the Open VSX registry that Code Editor uses), and
wired to **Amazon Bedrock in the same account** via `~/.claude/settings.json` (the doc-sanctioned
headless equivalent of the `/setup-bedrock` wizard) — no external Anthropic API key. It uses the
EC2 instance profile's `bedrock:InvokeModel*` grant. The primary model is pinned to Sonnet 4.6 and
the small/fast model to Haiku 4.5 (both pre-subscribed by the `ModelWarmup` custom resource) so
Claude Code never falls back to an unsubscribed Opus default (which would also bill at Opus rates).
The config write is best-effort (`set +e`): user-data runs under `set -euo pipefail` with **no**
`CreationPolicy`/cfn-signal, so an unguarded failure there would abort the rest of user-data
(including the Code Editor server install) while CloudFormation still reported `CREATE_COMPLETE` —
a bricked box. Worst case now is the participant sees the one-time `/setup-bedrock` wizard.
Ref: https://code.claude.com/docs/en/amazon-bedrock

## Three deploy invariants (each caused a Workshop Studio deployment failure until fixed)
1. **IAM analyzer — multi-valued condition keys need a set operator.**
   `static/iam/participant-write.json`'s `aws-marketplace:ProductId` (two product IDs) must sit
   under `ForAnyValue:StringEquals`, not plain `StringEquals`. A plain-`StringEquals` list is an
   `ACCESS_ANALYZER_FINDING_ERROR` at build time, and Workshop Studio then **refuses to stage the
   IAM policy** → deployment fails pre-CFN with `error getting iam policy json ... 404 NoSuchKey`.
2. **EC2 UserData ≤ 16 KB base64.** Keep the `code-editor-stack.yaml` UserData lean (this file
   exists because of that). Comment bloat in `!Sub |` counts against the limit.
3. **CMK-encrypted secret ⇒ callers need `kms:Decrypt`.** `EditorSecret` is encrypted with the
   customer-managed `EditorSecretKey` (CKV_AWS_149). `secretsmanager:GetSecretValue` decrypts using
   the **caller's** KMS permissions (via `kms:ViaService`) — the key policy's SecretsManager-service
   grant alone is not enough. Both `EditorRole` (EC2 user-data) and `UrlResolverRole` (custom
   resource) therefore carry `kms:Decrypt`/`kms:DescribeKey` on `EditorSecretKey.Arn`.
4. **IAM propagation race on `UrlResolverFn`.** Lambda `CreateFunction` can fail intermittently with
   *"The role defined for the function cannot be assumed by Lambda"* when `UrlResolverRole` was
   created only ~2s earlier and hasn't propagated to the Lambda control plane yet (IAM is eventually
   consistent). Observed: build `4573da2c`'s event deploy FAILED here (role complete `10:48:18`, Fn
   failed `10:48:20`); build `467e89ae` happened to win the race. Fix: `UrlResolverFn` has
   `DependsOn: ModelWarmup` — the ModelWarmup custom resource polls Bedrock for ~50s and always
   completes well after `UrlResolverRole` is created, guaranteeing ample propagation time without a
   bespoke wait resource. (`ModelWarmupFn` uses the same role-GetAtt pattern but never hit this
   because it's created early in the graph, long before it's invoked.)

## Content-rendering invariant — image paths must be `/static/images/...`
The current Workshop Studio renderer serves the repo tree **verbatim** under the build's static
prefix (`https://static.<region>.prod.workshops.aws/<build-id>/...`): it fetches the raw
`content/**/*.md` and renders it client-side. It does **not** collapse a `static/` dir to web-root
the way classic Hugo does. So a markdown image written as `![alt](/images/foo.png)` resolves to
`<build-id>/images/foo.png` → **HTTP 403** (nothing published there), while the file actually lives
at `<build-id>/static/images/foo.png` → **HTTP 200**. **Every image ref must be
`/static/images/...`.** Verified live in a participant session 2026-07-27 (build `467e89ae`):
`/static/images/module-1/00-genai-obs-before.png` loaded 1625×868; `/images/...` was broken
(`naturalWidth===0`). Prior CLAUDE.md guidance ("use `/images/...`") was backwards for this renderer
and had silently broken **all 21** screenshots — images were only first added in commit `671cd90`,
so no build had ever rendered them correctly. Guard: `grep -rn '](/images/' workshop/content` must
return 0 (all refs use `](/static/images/`).

## Workshop Studio asset/build pinning (operational)
Nested templates (`code-editor-stack.yaml` etc.) live **only** in the `ws-assets` bucket under
`<content-id>/templates/`, not in the git repo. Workshop Studio **snapshots the assets at build
time**, so a build's event deploys whatever template was in the bucket **when the build was
triggered**. Therefore: **sync assets to S3 *before* triggering the build**, then create the event
on that build. Re-syncing the bucket after a build does not change what that build's events deploy.
