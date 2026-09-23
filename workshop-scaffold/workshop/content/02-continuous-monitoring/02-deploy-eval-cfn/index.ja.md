---
title: "2.2 評価器のデプロイ"
weight: 20
---

:::alert{type="info" header="これはモジュール 1 とは別のスタックです"}
モジュール 1 では Transaction Search を有効にし、エージェントがテレメトリを出力するようにしました。このモジュールでは、その上に評価を追加する **新しい** スタック `edd-eval-and-obs` をデプロイします。エージェントのランタイムロググループ `/aws/bedrock-agentcore/runtimes/<SERVICE_NAME>` の存在を **保証** し (なければ作成し、モジュール 1 やエージェントがすでに作成していれば取り込み、評価器が必要とするセッションのインデックスポリシーを付けます)、さらに評価器と Online Evaluation Config を作成します。
:::

:::alert{type="info" header="テンプレートがロググループを通常のリソースとして宣言しない理由"}
モジュール 1 のパスがすでに `/aws/bedrock-agentcore/runtimes/<SERVICE_NAME>` を作成しています (Path B の `edd-observability` スタックが作成し、Path A では Runtime が最初の呼び出し時に作成します)。このテンプレートがそれを通常の `AWS::Logs::LogGroup` として宣言していたら、CloudFormation のデプロイ前検証が `AWS::EarlyValidation::ResourceExistenceCheck` でチェンジセットを拒否します。すでに存在する名前付きリソースを宣言的に作成することはできないからです。代わりにテンプレートは、ロググループを冪等に **作成または取り込む** 小さなカスタムリソースを使います。これは、別のスタックが所有しうるインフラの上に積み重なるスタックで真似する価値があるパターンです。
:::

## やること

`cfn/agentcore-eval-and-obs.yaml` をデプロイします。これは次のものを作成します。

- **評価器** (デフォルトは Builtin.Helpfulness)
- エージェントのロググループを監視する **Online Evaluation Config**
- 評価器にログの読み取りとジャッジモデルの呼び出しを許可する **eval-execution IAM ロール**

## スタックをデプロイする

**Path B (任意のフレームワーク、このワークショップの pi-mono) を選んだ場合:**

```bash
source /workshop/edd-workshop/config.env
cd /workshop/edd-workshop

aws cloudformation deploy \
  --stack-name edd-eval-and-obs \
  --template-file cfn/agentcore-eval-and-obs.yaml \
  --parameter-overrides \
    ServiceName=${SERVICE_NAME} \
    EvaluatorMode=Builtin \
    ArtifactsBucket=${ARTIFACTS_BUCKET} \
    ArtifactsPrefix=${ARTIFACTS_PREFIX} \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset
```

**Path A (AgentCore Runtime 上の Strands) を選んだ場合**、ロググループと出力される `service.name` が異なるため、Path A.2 の **両方の** 名前を渡します。

```bash
source /workshop/edd-workshop/config.env
cd /workshop/edd-workshop

# Both were captured in Path A.2. Re-derive them if this is a new shell.
echo "log suffix   = $RUNTIME_LOG_SUFFIX"     # e.g. myAgent-ABC123-DEFAULT
echo "service.name = $RUNTIME_SERVICE_NAME"   # e.g. myAgent.DEFAULT

aws cloudformation deploy \
  --stack-name edd-eval-and-obs \
  --template-file cfn/agentcore-eval-and-obs.yaml \
  --parameter-overrides \
    ServiceName=${RUNTIME_LOG_SUFFIX} \
    EmittedServiceName=${RUNTIME_SERVICE_NAME} \
    EvaluatorMode=Builtin \
    ArtifactsBucket=${ARTIFACTS_BUCKET} \
    ArtifactsPrefix=${ARTIFACTS_PREFIX} \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset
```

`CREATE_COMPLETE` を待ちます。新しいアカウントでは **4 〜 8 分** かかります。スタックはプロビジョナー Lambda と eval-execution ロールを構築し、その後 `CreateOnlineEvaluationConfig` を呼び出して安定するまで待ちます。

:::alert{type="warning" header="Path A: 2 つの異なる名前。さもなければ何も採点されません"}
`ServiceName` は評価器が読むロググループを構成します。`EmittedServiceName` は、その中のレコードに適用される `service.name` のフィルターです。AgentCore Runtime では、これらは **同じ** 文字列ではありません。ロググループはランタイム ID を保持し (`myAgent-ABC123-DEFAULT`)、レコードはドット連結の `myAgent.DEFAULT` を持ちます。

ログのサフィックスだけを渡すと、フィルターはどのレコードにも一致しません。設定は `ACTIVE` になり、エラーも表示されず、どのセッションも採点されません。`EmittedServiceName` を空のままにするのが正しいのは Path B だけで、そこでは 2 つの値が同一です。
:::

:::alert{type="warning" header="後で *もう一方* のパス用にこのスタックをデプロイしますか。EmittedServiceName を明示してください"}
`aws cloudformation deploy` は **渡さなかったパラメーターをすべて保持します**。そのため、このスタックが Path A 用にすでにデプロイされており、今回 Path B 用に `ServiceName=${SERVICE_NAME}` だけを指定してデプロイすると、スタックは Path A の `EmittedServiceName` を黙って保持します。テンプレートはフィルターを「`EmittedServiceName` が設定されていればそれ、なければ `ServiceName`」として計算するため、**Path B のロググループ** を読みながら **Path A のサービス名** でフィルターする設定になります。`ACTIVE` で、エラーもなく、採点されるセッションはゼロです。

Path A を先に実施したアカウントでの実測です。上の Path B のデプロイを `EmittedServiceName` なしで行った後:

```
logGroupNames: ["/aws/bedrock-agentcore/runtimes/travel-agent-edd-workshop"]   <- Path B
serviceNames:  ["travelAgentStrands_travelAgent.DEFAULT"]                      <- still Path A
```

明示的に渡せば解決し、値がすでに等しい場合でも無害です。

```bash
aws cloudformation deploy \
  --stack-name edd-eval-and-obs \
  --template-file cfn/agentcore-eval-and-obs.yaml \
  --parameter-overrides \
    ServiceName=${SERVICE_NAME} \
    EmittedServiceName=${SERVICE_NAME} \
    EvaluatorMode=Builtin \
    ArtifactsBucket=${ARTIFACTS_BUCKET} \
    ArtifactsPrefix=${ARTIFACTS_PREFIX} \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset
```

知っておく価値のある副作用が 2 つあります。修正後のデプロイは **新しい** 設定を作成し (名前はサービス名から導出されます)、**古い設定を ACTIVE のまま残します**。古いほうを削除しないと、ジャッジを呼び出し続けます。また設定が 2 つ存在すると、`onlineEvaluationConfigs[0]` はどちらを返すかわかりません。これは 4.2 のステップ 1 が結果のロググループについて警告しているのと同じ罠です。インデックスではなく名前で解決してください。
:::

:::alert{type="info" header="なぜ CAPABILITY_IAM ではなく CAPABILITY_NAMED_IAM なのか"}
このスタックは、Online Evaluation Config が安定した ARN を参照できるように、eval-execution ロールを **明示的な名前** (`${ProjectName}-eval-exec`) で作成します。名前付きの IAM リソースを含むテンプレートには `CAPABILITY_NAMED_IAM` が必要です。`CAPABILITY_IAM` だけだと、デプロイは即座に `InsufficientCapabilitiesException: Requires capabilities : [CAPABILITY_NAMED_IAM]` で失敗します。(`CAPABILITY_NAMED_IAM` は上位集合なので、スタック内の名前なしロールもカバーします。)
:::

:::alert{type="warning" header="デプロイが ROLLBACK_COMPLETE / IAM ロール名の競合でロールバックしましたか"}
スタックの `ProjectName` パラメーターはデフォルトで `edd-workshop` になり、その **固定の** IAM ロール名 (`${ProjectName}-eval-exec`) を構成するのに使われます。Workshop Studio がプロビジョニングしたサンドボックス (イベントごとに新しいアカウント 1 つ) では、これが衝突することはありません。ただし、共有または再利用された AWS アカウントでこのモジュールを再実行している場合 (ローカルで練習している、または以前の試行の後に再デプロイしている場合)、デフォルトの `ProjectName` での 2 回目のデプロイはそのロール名で衝突し、ロールバックします。

対処: 一意な `ProjectName` の上書きを渡します。

```bash
aws cloudformation deploy \
  --stack-name edd-eval-and-obs \
  --template-file cfn/agentcore-eval-and-obs.yaml \
  --parameter-overrides \
    ServiceName=${SERVICE_NAME} \
    EvaluatorMode=Builtin \
    ArtifactsBucket=${ARTIFACTS_BUCKET} \
    ArtifactsPrefix=${ARTIFACTS_PREFIX} \
    ProjectName=edd-workshop-$(date +%s | tail -c 6) \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset
```
:::

## 設定が有効であることを確認する

スタックが完了したら、Online Evaluation Config が作成され、有効になっていることを確認します。

```bash
aws bedrock-agentcore-control list-online-evaluation-configs \
  --region us-east-1 \
  --query 'onlineEvaluationConfigs[?contains(onlineEvaluationConfigName, `edd_workshop`)].{name:onlineEvaluationConfigName, status:status}' \
  --output table
```

`status: ACTIVE` を示す 1 行のテーブルが表示されるはずです。

:::alert{type="warning" header="評価器のコマンドには最近の AWS CLI v2 が必要です"}
`bedrock-agentcore-control` の評価器 / online-evaluation のサブコマンド (`list-online-evaluation-configs`、`list-evaluators`、`create-evaluator` など) には、最近の **AWS CLI v2** が必要です。古い CLI では上のコマンドが次のように失敗します。

```
aws: error: argument operation: Invalid choice, valid choices are: ...
```

Workshop Studio の Code Editor は最新の CLI をインストールするため、通常はすでに動作します。このエラーが出た場合は確認してアップグレードしてください (macOS と Linux のインストールコマンドは、モジュール 00 の CLI アップグレードの注記を参照)。

```bash
aws --version                       # upgrade if a subcommand reports Invalid choice
```

ここではアップグレードしか選択肢がありません。Code Editor には `boto3` も、それをインストールする `pip` も入っていないため、Python のフォールバックは存在しません。
:::

:::alert{type="warning" header="どちらの名前をどちらのパラメーターに入れるか"}
評価器はロググループ `/aws/bedrock-agentcore/runtimes/<ServiceName>` を読み、その中のレコードを `service.name` でフィルターします。2 つのパラメーター、2 つの異なる役割です。

| モジュール 1 のパス | `ServiceName` がロググループを構成 | `EmittedServiceName` がレコードをフィルター |
|---|---|---|
| **Path B** (任意のフレームワーク、このワークショップの pi-mono) | `travel-agent-edd-workshop`、`config.env` のデフォルト | 省略してください。Path B では 2 つの値が同一です |
| **Path A** (AgentCore Runtime 上の Strands) | `$RUNTIME_LOG_SUFFIX`、ハイフン連結、ランタイム ID を保持 | `$RUNTIME_SERVICE_NAME`、ドット連結、ランタイム ID を除外 |

わからない場合は、Runtime が実際に作成した名前を読んでください。

```bash
aws logs describe-log-groups \
  --log-group-name-prefix /aws/bedrock-agentcore/runtimes/ \
  --query 'logGroups[*].logGroupName' --output table
```

Path A ではこれが 1 行を表示します。たとえば `/aws/bedrock-agentcore/runtimes/travelAgentStrands_travelAgent-IDyHBY845c-DEFAULT` です。`runtimes/` より後ろがすべて `ServiceName` です。
:::

## スタックが作成したもの

スタックは 3 つのリソースをデプロイしました。

1. **評価器**: `Builtin.Helpfulness` として登録されます (AWS 管理の既存の評価器で、スタックはそれを参照します)。
2. **Online Evaluation Config**: 名前は `edd_workshop_` で始まり、その後にサービス名が続きます。エージェントのロググループを監視し、完了したセッションごとに評価器を呼び出します。

   末尾ではなくこの **接頭辞** で照合してください。設定名は 48 文字が上限のため (`^[a-zA-Z][a-zA-Z0-9_]{0,47}$`)、Path A のサービス名ではプロビジョナーが切り詰め、`edd_workshop_travelAgentStrands_travelAgent_DEFA` のように末尾の `_helpfulness` が完全に切り落とされたものになります。
3. **Eval Execution Role**: 評価サービスがログイベントを読み、スコアを書き込むために引き受ける IAM ロール。

評価器はこれで稼働しています。エージェントのロググループに現れる新しいセッションは、セッションのアイドルタイムアウト後に取り上げられ、自動的に採点されます。
