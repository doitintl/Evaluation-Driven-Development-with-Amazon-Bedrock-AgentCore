---
title: "Path B.2 可観測性インフラのデプロイ"
weight: 20
---

アダプターにはスパンの送信先が必要です。このステップでそれをデプロイします。ワークスペースに配置済みの小さな CloudFormation テンプレート 1 つです。

## ステップ 1: スタックをデプロイする

:::code{language=bash showCopyAction=true showLineNumbers=false}
source /workshop/edd-workshop/config.env
cd /workshop/edd-workshop

aws cloudformation deploy \
  --stack-name edd-observability \
  --template-file cfn/agentcore-observability.yaml \
  --parameter-overrides ServiceName=${SERVICE_NAME} \
  --capabilities CAPABILITY_IAM \
  --no-fail-on-empty-changeset \
  --region us-east-1
:::

`Successfully created/updated stack` を待ちます (2 〜 4 分)。

## ステップ 2: 3 つの要素すべてを確認する

**まず予測してください。** 新しいアカウントで、このデプロイ前からすでに存在していたのはどれでしょうか。`aws/spans` ロググループ、エージェントのロググループ、それともどちらでもない。(モジュール 0 の空のダッシュボードがヒントです。)

:::code{language=bash showCopyAction=true showLineNumbers=false}
# 1. Where do traces go? (Transaction Search on = CloudWatchLogs)
aws xray get-trace-segment-destination --region us-east-1

# 2. The agent's log group.
aws logs describe-log-groups \
  --log-group-name-prefix /aws/bedrock-agentcore/runtimes/${SERVICE_NAME} \
  --region us-east-1 --query 'logGroups[].logGroupName' --output text

# 3. The spans log group.
aws logs describe-log-groups --log-group-name-prefix aws/spans \
  --region us-east-1 --query 'logGroups[].logGroupName' --output text
:::

期待される結果:

1. `"Destination": "CloudWatchLogs"`。`"Status"` は最初 `PENDING` です。ステップ 3 を参照してください。
2. `/aws/bedrock-agentcore/runtimes/travel-agent-edd-workshop`
3. `aws/spans`

**答え:** どちらも存在していませんでした。新しいアカウントは `Destination: XRay` で始まり、ロググループはありません。これがまさにモジュール 0 のダッシュボードが空だった理由です。デフォルトでエージェントを観測するものはなく、このパイプラインのすべての要素は、何かがデプロイしたからこそ存在します。

## ステップ 3: Transaction Search が ACTIVE になるまで待つ

:::alert{type="warning" header="ACTIVE と表示されるまでエージェントを実行しないでください"}
保存先がまだ `PENDING` の間、X-Ray は OTLP のスパンを `400 Bad Request` で拒否します。そのため、アダプターが完璧でも Path B.4 がエクスポートエラーで失敗します。

```bash
aws xray get-trace-segment-destination --region us-east-1 --query 'Status' --output text
```

スタック完了から `ACTIVE` まで **6 〜 10 分** を見込んでください。安定するのを待つ間にアダプター (Path B.3) を構築しましょう。B.4 は、依存する前にパイプラインがスパンを受け付けていることを確認するチェックから始まります。
:::

## スタックが実際に作成したもの

:::alert{type="info" header="仕組み: 3 つの要素と、それぞれが必要な理由"}
1. **Transaction Search の配線**: X-Ray のトレース保存先を CloudWatch Logs に切り替え、OTLP のスパンが `aws/spans` に届くようにします。また、X-Ray がそこに書き込むために必要なリソースポリシーを付与します。
2. **エージェントのロググループ** `/aws/bedrock-agentcore/runtimes/<service.name>`。アダプターが `aws.log.group.names` リソース属性で指定するものです。
3. 両方のロググループへの **フィールドインデックスポリシー**。モジュール 2 の評価器が `service.name` と `session.id` でセッションを解決できるようにします。

`SERVICE_NAME` (デフォルトは `travel-agent-edd-workshop`) はパイプライン全体の結合キーです。ロググループ名、アダプターの OTEL `service.name`、モジュール 2 の評価設定がすべてこれをキーにします。

このステップはどのフレームワークでも同一です。フレームワークごとの違いが出るのは Path B.3 のアダプターだけです。
:::

:::alert{type="info" header="仕組み: Transaction Search はアカウントレベルで 1 回だけ"}
保存先の切り替えと `aws/spans` グループは、アカウントごと、リージョンごとです。すでに Transaction Search を有効にしている場合 (たとえば Path A を先に実施した場合)、テンプレートがそれを検知してその部分をスキップします。エージェント単位の要素は、指定した `ServiceName` に対して引き続き作成されます。
:::

:::alert{type="warning" header="保存先が XRay のままの場合、またはスタックが TxnSearchEnable で失敗する場合"}
Transaction Search の有効化には 3 つのものが必要です。Lambda のロググループ `/aws/lambda/edd-observability-txn-search` が、どれが欠けているかを教えてくれます。

| Lambda ログのエラー | 不足しているもの |
|---|---|
| `not authorized to perform: application-signals:StartDiscovery` | 呼び出し元の IAM 権限。`UpdateTraceSegmentDestination` が代わりに Application Signals の `StartDiscovery` を呼ぶため、呼び出し元にはこのアクションと、`AWSServiceRoleForCloudWatchApplicationSignals` のための `iam:CreateServiceLinkedRole` が必要です。最もよくある致命的な失敗です。 |
| `XRay does not have permission to call PutLogEvents on the aws/spans Log Group` | `xray.amazonaws.com` に `log-group:aws/spans:*` への `logs:PutLogEvents` を付与する CloudWatch Logs のリソースポリシー (注意: `aws/spans`、先頭スラッシュなし)。テンプレートの Lambda が作成しますが、競合する既存ポリシーがあるとブロックされることがあります。`aws logs describe-resource-policies --region us-east-1` で確認してください。 |
| `Updates are not allowed while the current status is PENDING` | 問題はありません。変更が進行中です。ステータスが `PENDING` を抜けるまで待ってから再試行してください。 |

3 つすべてが満たされていれば、カスタムリソースは 10 秒以内に完了します。
:::

**次: [Path B.3 アダプターの構築](../03-build-adapter/)。**
