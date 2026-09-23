---
title: "2.6 (任意) カスタム評価器"
weight: 55
---

:::alert{type="info" header="任意のステップ"}
このステップは任意です。時間が足りない場合は、サマリーへ進んでください。後で戻ってくることもできます。
:::

## なぜカスタムにするのか

`Builtin.Helpfulness` は汎用の品質スコアです。エージェントがドメイン固有の制約を尊重したかは判断できません。たとえば、Grand Museum が月曜休館であることや、`plan_route` より前に `query_sites` を呼ばなければならないことです。

**カスタム評価器** を使えば、ルーブリックと 1-5 のスケールで、ご自身のユースケースにとって「良い」とは何かを正確に定義できます。

## Custom モードで再デプロイする

ドメイン固有のルーブリックを持つカスタム評価器を使うようスタックを更新します。**ステップ 2.2 で使ったのと同じ名前のパラメーターを渡し**、変更するのは `EvaluatorMode` だけです。

**Path B (任意のフレームワーク、このワークショップの pi-mono) を選んだ場合:**

```bash
source /workshop/edd-workshop/config.env
cd /workshop/edd-workshop

aws cloudformation deploy \
  --stack-name edd-eval-and-obs \
  --template-file cfn/agentcore-eval-and-obs.yaml \
  --parameter-overrides \
    ServiceName=${SERVICE_NAME} \
    EvaluatorMode=Custom \
    ArtifactsBucket=${ARTIFACTS_BUCKET} \
    ArtifactsPrefix=${ARTIFACTS_PREFIX} \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset
```

**Path A (AgentCore Runtime 上の Strands) を選んだ場合**、ステップ 2.2 とまったく同じく **両方の** 名前を渡します。

```bash
source /workshop/edd-workshop/config.env
cd /workshop/edd-workshop

echo "log suffix   = $RUNTIME_LOG_SUFFIX"     # e.g. myAgent-ABC123-DEFAULT
echo "service.name = $RUNTIME_SERVICE_NAME"   # e.g. myAgent.DEFAULT

aws cloudformation deploy \
  --stack-name edd-eval-and-obs \
  --template-file cfn/agentcore-eval-and-obs.yaml \
  --parameter-overrides \
    ServiceName=${RUNTIME_LOG_SUFFIX} \
    EmittedServiceName=${RUNTIME_SERVICE_NAME} \
    EvaluatorMode=Custom \
    ArtifactsBucket=${ARTIFACTS_BUCKET} \
    ArtifactsPrefix=${ARTIFACTS_PREFIX} \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset
```

:::alert{type="warning" header="Path A: EmittedServiceName を省くと、すべての採点が黙って止まります"}
`aws cloudformation deploy` がパラメーターの **以前の** 値を保持するのは、`--parameter-overrides ... EmittedServiceName=` を明示的に渡す場合か、デフォルト値を持つテンプレートからそのパラメーターを省略した場合だけです。ここでこれを落として `ServiceName=${SERVICE_NAME}` だけを渡すと、再生成された設定は誤ったロググループを監視しながら、誤った `service.name` でフィルターすることになります。

この失敗は目に見えません。スタックは `UPDATE_COMPLETE` を報告し、設定は `ACTIVE` を報告し、**採点されるセッションはゼロ** です。実際のアカウントでの実測では、不一致の設定は 0 件のイベントを記録し、正しくパラメーター設定されたものは 2 件を記録しました。25 分経っても `read-eval-scores.sh` が何も返さない場合は、まずこれを確認してください。
:::

`UPDATE_COMPLETE` を待ちます。**4 〜 8 分** を見込んでください。この更新は Online Evaluation Config を削除して再作成します。

:::alert{type="info" header="UPDATE_COMPLETE を信じるだけでなく、確認してください"}
これは既存のデプロイに対して `EvaluatorMode` を切り替える、同一スタックのインプレース更新です。CloudFormation が `UPDATE_COMPLETE` を報告することはスタック更新の成功を確認しますが、それだけでは Online Evaluation Config に評価器がまだアタッチされていることを証明しません。まず設定が存在し有効であることを確認します。

```bash
aws bedrock-agentcore-control list-online-evaluation-configs \
  --region us-east-1 \
  --query 'onlineEvaluationConfigs[?contains(onlineEvaluationConfigName, `edd_workshop`)].{name:onlineEvaluationConfigName, status:status}' \
  --output table
```

`ACTIVE` は必要条件ですが十分ではありません。評価器が **1 つも** アタッチされていない設定も `ACTIVE` を報告し、黙って何も採点しません。そこでアタッチ状態そのものを読みます。

```bash
CFG=$(aws bedrock-agentcore-control list-online-evaluation-configs \
  --region us-east-1 \
  --query 'onlineEvaluationConfigs[0].onlineEvaluationConfigId' --output text)

aws bedrock-agentcore-control get-online-evaluation-config \
  --online-evaluation-config-id "$CFG" --region us-east-1 \
  --query '[status,evaluators]' --output json
```

期待される結果です (サフィックスはご自身のもの)。

```json
[
  "ACTIVE",
  [
    {
      "evaluatorId": "edd_workshop_travel_quality-XXXXXXXXXX"
    }
  ]
]
```

読み取るべき点が 2 つあります。リストが **空でない** こと、そして `Builtin.Helpfulness` が **なくなっている** ことです。この切り替えは評価器を追加するのではなく置き換えます。(フィールド名は `evaluators` で、`evaluatorConfigs` は存在しません。)

設定が見つからない、ステータスが `ACTIVE` でない、あるいは `evaluators` が空の場合、インプレースの切り替えを繰り返し再試行するのではなく、スタックを削除して目的のモードで新規にデプロイし直すのが最も安全な復旧方法です。

```bash
aws cloudformation delete-stack --stack-name edd-eval-and-obs
aws cloudformation wait stack-delete-complete --stack-name edd-eval-and-obs
# then re-run the deploy command above
```
:::

## 変わったこと

スタックは、旅行ドメインのルーブリックを使ってセッションを 1-5 のスケールで採点する **カスタム評価器** を作成するようになりました。ルーブリックはジャッジモデルに次の確認を指示します。

- エージェントは観光地と営業時間について正確な情報を提供したか。
- 既知の制約 (休業日、予約要件など) を尊重したか。
- 応答はよく構成され、実行に移せるものだったか。

Online Evaluation Config は、`Builtin.Helpfulness` の代わりにこのカスタム評価器を使うよう更新されます。

## 新しいトラフィックを生成する

ステップ 2.3 と同じ方法で、ドメインの理解を試すクエリでエージェントを呼び出します。

```bash
# Path B (this workshop's pi-mono OpenInference adapter)
cd /workshop/edd-workshop/openinference-aws-adapter
USER_QUERY="Plan a Monday visit to the Grand Museum in Luminara" npm start
USER_QUERY="What is open on Sunday morning in Luminara?"          npm start
```

:::alert{type="info" header="Path A"}
Path A (AgentCore Runtime 上の Strands) を選んだ場合は、代わりに `travel-agent-strands/` から `agentcore invoke "<query>"` でトラフィックを生成してください。
:::

## カスタムスコアを確認する

最大 20-25 分見込んでから (ステップ 2.1 のタイミングの注記を参照)、評価用ロググループを確認します。

```bash
cd /workshop/edd-workshop
./scripts/read-eval-scores.sh
```

ここでは `--limit` ではなく `--max-items` を使ってください。理由はステップ 2.3 の警告を参照してください。

## 期待される出力

カスタム評価器のスコアは 0.0-1.0 ではなくルーブリックの 1-5 スケールを使い、ルーブリックが定義したラベルを持ちます。

```
Reading /aws/bedrock-agentcore/evaluations/results/edd_workshop_..._DEFA-h8MFHfGuoF

  edd_workshop_travel_quality (2 score(s))
    session b0be1052-5454-4edc-adc   score=4.0   Very Good
      Evaluating the agent's response across three dimensions:
      1. FACTUAL ACCURACY: The response presents a well-organized table of attractions...
    session 324a4efc-bfb9-4238-ad3   score=4.0   Very Good
      ...

  2 score(s) across 1 evaluator(s)
```

元になるログレコードは、同じ値を OTEL 属性として持ちます。

```json
{
  "gen_ai.evaluation.name": "edd_workshop_travel_quality",
  "gen_ai.evaluation.score.value": 4,
  "gen_ai.evaluation.score.label": "Very Good",
  "gen_ai.evaluation.explanation": "Let me evaluate this response across the three dimensions: 1. FACTUAL ACCURACY: ...",
  "session.id": "3e869096-2f71-4c5b-913c-0edef93c1c3d"
}
```

実際のレコードで実測した詳細が 2 つあります。評価器は `gen_ai.evaluation.name` として届きます。`Builtin.Helpfulness` が使っていたのと同じキーなので、ステップ 2.3 で書いたクエリはそのまま動作し続けます。そして **レコード内の名前にはサフィックスがありません**。設定はサービスが生成したサフィックス付きの `edd_workshop_travel_quality-XXXXXXXXXX` を参照する一方、スコアレコードには単に `edd_workshop_travel_quality` と書かれています。レコードをフィルターするときは素の名前で照合し、API 経由で評価器を指定するときはサフィックス付きの id で照合してください。

`Builtin.Helpfulness` はもうまったく現れません。設定がその代わりにご自身の評価器を実行しているからです。

## 2 つのアプローチを比較する

| | Builtin.Helpfulness | カスタム評価器 |
|---|---|---|
| **スケール** | 0.0-1.0 (浮動小数点) | 1-5 (整数) |
| **セットアップ** | 設定不要 | ルーブリックの作成が必要 |
| **ドメインの理解** | 汎用的な品質 | ドメイン固有の制約 |
| **ユースケース** | 広範な品質の煙感知器 | 自分のドメインに対する精密な採点 |

2 つのアプローチは異なる目的に役立ちます。本番環境では **両方** を動かすこともあります。一般的な品質モニタリングには Builtin を、ドメイン固有のリグレッション検出には Custom を使います。
