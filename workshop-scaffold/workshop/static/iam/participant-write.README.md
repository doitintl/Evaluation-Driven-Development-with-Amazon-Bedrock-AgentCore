# `participant-write.json` — IAM rationale

This file is the inline IAM policy attached to `WSParticipantRole` via
`contentspec.yaml.awsAccountConfig.participantRole.iamPolicies`.
JSON does not support inline comments, so this README documents the
rationale for each `Sid`.

## Statements

### `CFNDeployEvalAndObsStack`

CloudFormation deploy actions scoped to the workshop's two stack name
prefixes (`edd-eval-and-obs/*` and `main-stack/*`). Participants run
`aws cloudformation deploy` against the eval+obs stack in Module 1
step 02; the main-stack scope is for the (rare) manual rollback path.

### `BedrockInvokeForJudgeAndAgent`

Bedrock invoke scoped to `foundation-model/*` + `inference-profile/*`.
Wildcard region in the foundation-model ARN is intentional: cross-region
inference profiles route to multiple regions in the geography (e.g.,
`us.anthropic.claude-sonnet-4-6` may execute in any of us-east-1,
us-east-2, or us-west-2), so a region-pinned ARN would 403.

### `BedrockMarketplaceSubscribeAnthropicProducts` + `BedrockMarketplaceViewSubscriptions`

`aws-marketplace:Subscribe` is scoped via the
`aws-marketplace:ProductId` Condition key to the two Anthropic Claude
product IDs the workshop uses:
- `prod-ffvjxvh4ltq64` (Anthropic Claude Sonnet 4.6)
- `prod-xdkflymybwmvi` (Anthropic Claude Haiku 4.5)

Reference: [Use product ID condition keys to control access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access-product-ids.html).

Amazon Nova / Meta / Mistral / DeepSeek / Qwen / OpenAI models are not
sold via AWS Marketplace and don't have product IDs (per the same doc),
so they don't appear here.

`aws-marketplace:ViewSubscriptions` is split into its own statement
because it's a read-only API that AWS does not gate by ProductId.
Both statements add `aws:RequestedRegion: us-east-1` Condition.

### `AgentCoreEvalManagement`

Full AgentCore eval CRUD on `evaluator/*` and `online-evaluation-config/*`
ARNs only — never agent runtime ARNs, never browser/gateway/memory ARNs.

### `PassEvalRolesToServices`

`iam:PassRole` scoped to `role/edd-eval-and-obs-*` and `role/edd-workshop-*`
only. The participant cannot pass any other role.

### `ManageWorkshopIAMRolesAndPolicies`

Full IAM role + policy CRUD scoped to `role/edd-eval-and-obs-*` +
`role/edd-workshop-*` only. CloudFormation needs this to provision
the eval+obs stack's execution role.

### `ServiceLinkedRoleCreationForWorkshopServices`

`iam:CreateServiceLinkedRole` scoped to four specific service-link role
paths (`bedrock-agentcore`, `application-signals`, `cloudtrail`,
`observability.aoss`) — the only services the workshop creates SLRs for.

### `ManageWorkshopLambdaFunctions`

Full Lambda CRUD scoped to `function:edd-eval-and-obs-*` and
`function:edd-workshop-*` only. Custom resources in the eval+obs stack
need this.

### `ManageWorkshopLogGroups`

CloudWatch Logs CRUD + index-policy management scoped to:
- `/aws/bedrock-agentcore/*` — agent runtime log groups
- `/aws/lambda/edd-eval-and-obs-*` and `/aws/lambda/edd-workshop-*`
- `aws/spans` — the X-Ray Transaction Search log group

### `AccountLevelTransactionSearchControlsNoResourceArnAvailable`

`xray:UpdateTraceSegmentDestination`, `xray:UpdateIndexingRule`,
`application-signals:StartDiscovery`, and
`cloudtrail:CreateServiceLinkedChannel` on `Resource: "*"`.

**Why `Resource: "*"` is the only option here:** these are
account-level AWS service actions that **do not support
resource-level permissions** per the IAM service-authorization
reference for each service:

- [xray actions](https://docs.aws.amazon.com/service-authorization/latest/reference/list_awsx-ray.html) — `UpdateTraceSegmentDestination` and `UpdateIndexingRule` are listed under "Actions defined by AWS X-Ray" with **Resource Type: (none)**, meaning IAM only accepts `Resource: "*"`. The Transaction Search destination + indexing rule are account-singular configuration objects (one per region), not per-resource entities.
- [application-signals actions](https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazoncloudwatchapplicationsignals.html) — `StartDiscovery` is the account-level enable-flip for the Application Signals service-linked role; same "Resource Type: (none)" classification.
- [cloudtrail actions](https://docs.aws.amazon.com/service-authorization/latest/reference/list_awscloudtrail.html) — `CreateServiceLinkedChannel` registers the Transaction Search subscription channel; account-level, "Resource Type: (none)".

**Mitigations applied:** the `aws:RequestedRegion: us-east-1`
Condition restricts the surface to the workshop's deployment region
(the AWS-recommended pattern for account-level actions per the
[IAM least-privilege guide](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html#grant-least-privilege)).
Cloudsplaining (the analyzer Holmes uses) accepts a Condition as a
valid scoping constraint and clears CKV_AWS_111 on this Sid. The Sid
name itself (`*NoResourceArnAvailable`) encodes the constraint so it
is greppable in audit tooling.

### `DeployerCustomResourceWriteWorkshopObjects`

S3 PutObject + DeleteObject scoped to `edd-workshop-*/*` object ARNs
(used by the SPA deployer's CFN custom resource).

### `DeployerCustomResourceTagWorkshopBuckets`

`s3:PutBucketTagging` scoped to `edd-workshop-*` bucket ARN (used by
the network stack's tagger custom resource). Bucket-level Action with
a bucket-level ARN — no overlap with the object-level statement.

## Why inline rather than AWS-managed

No AWS-managed policy provides the exact Bedrock + AgentCore + CFN +
Lambda + Logs scope this workshop needs, AND no AWS-managed policy
expresses the workshop's per-resource ARN scoping. Inline policies
disappear cleanly with the role on stack delete, leaving no
customer-managed-policy residue in the participant's sandbox.
