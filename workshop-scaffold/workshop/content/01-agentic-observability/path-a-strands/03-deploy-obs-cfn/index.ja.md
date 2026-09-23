---
title: "Path A.3 可観測性インフラのデプロイ"
weight: 30
---

**シナリオ。** エージェントは Runtime 上で動作し、サイドカーはすでにテレメトリを出力しようとしていますが、アカウントにはまだスパンを保持する場所がありません。**このステップを飛ばすと、モジュール 1 はトレースを生成せず、ダッシュボードは空のままで、モジュール 2 は何も採点できません。** CloudFormation のデプロイ 1 回で解決します。2 〜 4 分です。

## 1 回のデプロイで有効になるもの

```bash
source /workshop/edd-workshop/config.env
cd /workshop/edd-workshop

aws cloudformation deploy \
  --stack-name edd-observability \
  --template-file cfn/agentcore-observability.yaml \
  --parameter-overrides ServiceName=${RUNTIME_LOG_SUFFIX} \
  --capabilities CAPABILITY_IAM \
  --no-fail-on-empty-changeset
```

`Successfully created/updated stack` を待ちます。

`${RUNTIME_LOG_SUFFIX}` は Path A.2 で実行したスクリプトによる値で、`config.env` がどのターミナルでも供給します。これは名前のロググループ形式で、このテンプレートが必要とするものです。

:::alert{type="warning" header="ServiceName が空だと言われてデプロイが失敗する場合"}
`config.env` にまだ値がありません。Path A.2 の取得ステップを実行してください。

```bash
cd /workshop/edd-workshop && ./scripts/capture-runtime-names.sh && source config.env
```
:::

:::alert{type="info" header="学習: Transaction Search とは何か、ダッシュボードがなぜそれを必要とするのか"}
**AWS X-Ray** は AWS の分散トレーシングサービスです。スパン (リクエスト内の計時された作業単位) を収集し、呼び出し経路を示すトレースに組み立てます。エージェントにとって、そのトレースこそが *トラジェクトリ* です。どのツールがどの順番で実行され、それぞれどれだけ時間がかかったかです。
[X-Ray のドキュメント](https://docs.aws.amazon.com/xray/latest/devguide/aws-xray.html)

デフォルトでは、X-Ray はトレースをサンプリングして自身のバックエンドに保持し、X-Ray API 経由でのみアクセスできます。レイテンシのデバッグには十分ですが、評価には役立ちません。評価はサンプルではなく全セッションを必要とし、属性でクエリする必要があります。

**Transaction Search** は保存先を変えます。有効にすると、X-Ray はスパンの 100% を `aws/spans` という CloudWatch ロググループに構造化レコードとして書き込みます。この 1 つの変更が、スパンを `service.name` と `session.id` でクエリできるようにし、GenAI Observability ダッシュボードとモジュール 2 の評価器の両方がこれを読み取ります。

これがなければ、ダッシュボードは空のままで、どのセッションも採点できません。
[Transaction Search のドキュメント](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Transaction-Search.html)

これは **アカウントレベル** の設定でエージェント単位ではないため、1 回有効にすればアカウント内のすべてのエージェントに適用されます。
:::

:::alert{type="info" header="仕組み: スタックが作るもの、そしてなぜテンプレートなのか"}
| リソース | 目的 |
|---|---|
| Transaction Search の配線 | X-Ray のトレース保存先を `aws/spans` ロググループに向ける |
| ロググループのインデックスポリシー | `service.name` と `session.id` をインデックス化し、Logs Insights のクエリを高速に保つ |

X-Ray の保存先 API にはネイティブな CloudFormation リソースがないため、小さな Lambda カスタムリソースがこれを呼び出します。コンソールでクリックするのではなくテンプレートとしてデプロイすることで、ご自身のアカウントに持ち帰れるものが手元に残ります。

このスタックはエージェントのロググループを **作成しません**。それは Runtime が最初の呼び出し時に作成しました。評価リソースも作成しません。それはモジュール 2 の役割です。
:::

## 確認

ロググループが存在するかどうかだけでなく、トレースの **保存先** を確認します。`aws/spans` グループが存在していても、トレースがまだ X-Ray のバックエンドに行っていることがあります。

```bash
aws xray get-trace-segment-destination --region us-east-1
```

期待される結果: `"Destination": "CloudWatchLogs"` と `"Status": "ACTIVE"`。

切り替え直後は `ACTIVE` になるまで **6 〜 10 分** かかるため、ここで `PENDING` が出るのは正常です。**座って待たないでください。** Path A.4 は、パイプラインが実際にスパンを受け付けているかを確認するチェックから始まります。これはこのステータスより強いテストで、その間に何をすべきかも示します。

:::alert{type="warning" header="保存先がまだ XRay の場合、またはスタックが TxnSearchEnable で失敗した場合"}
Lambda のロググループ (`/aws/lambda/edd-observability-txn-search`) に原因が書かれています。Transaction Search を有効にすると、X-Ray が代わりに複数の API を呼び出し、それぞれに固有の権限が必要です。

| Lambda ログのエラー | 不足しているもの |
|---|---|
| `not authorized to perform: application-signals:StartDiscovery` | 呼び出し元の権限。`UpdateTraceSegmentDestination` が代わりに Application Signals の `StartDiscovery` を呼ぶため、呼び出し元にはこれと `iam:CreateServiceLinkedRole` が必要です。 |
| `not authorized to perform: logs:PutRetentionPolicy` | 同じ呼び出しが `aws/spans` に保持期間を設定します。 |
| `XRay does not have permission to call PutLogEvents on the aws/spans Log Group` | `xray.amazonaws.com` が `log-group:aws/spans:*` に書き込めるようにする CloudWatch Logs のリソースポリシー (先頭にスラッシュがないことに注意)。テンプレートの Lambda が作成しますが、競合する既存ポリシーがあるとブロックされることがあります。 |
| `Updates are not allowed while the current status is PENDING` | 問題はありません。変更が進行中です。ステータスが `PENDING` を抜けるまで待ってから再試行してください。 |

ワークショップのテンプレートはこれらすべてを付与しているため、新しいアカウントなら初回の試行で 10 秒以内に完了するはずです。
:::

## 現在の状態

アカウントがスパンを保持できるようになりました。まだ何も記録されていません。テレメトリは、パイプラインが稼働した後に発生した呼び出しのみを捕捉するからです。それが Path A.4 で、まさにその確認から始まります。
