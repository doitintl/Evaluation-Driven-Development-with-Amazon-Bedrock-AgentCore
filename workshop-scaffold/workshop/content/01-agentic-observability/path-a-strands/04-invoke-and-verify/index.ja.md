---
title: "Path A.4 呼び出しと確認"
weight: 40
---

**シナリオ。** エージェントはデプロイされ、可観測性も配線されましたが、まだ何も記録されていません。テレメトリはパイプラインが稼働した *後* の呼び出しにしか存在しません。このステップで最初の実際の証跡、つまり目に見えるセッションと、モジュール 2 が採点できるトラジェクトリを生成します。

## 4.1: パイプラインがスパンを受け付けていることを確認する

呼び出しの **前に** 実施してください。Transaction Search は Path A.3 の後、有効化の完了までに数分かかります。そして **準備完了前に出力されたスパンは拒否され、永久に失われます**。1 つのコマンドで判断できます。

```bash
cd /workshop/edd-workshop
./scripts/verify-telemetry.sh
```

現時点では、チェック 2 は成功し (Path A.2 のスモークテストがすでにレコードを書き込んでいます)、チェック 3 は「no spans」で失敗すると予想されます。取り込みが稼働してからエージェントを呼び出していないためです。待っているのはチェック 1 で、`destination=CloudWatchLogs status=ACTIVE` と表示されることを目指します。

**チェック 1 が `PENDING` の場合、この段階では正常な状態です。** スクリプトはそれを失敗として報告します。壊れてはいません。下の注記を参照してください。

:::alert{type="warning" header="チェック 1 が PENDING の場合"}
Path A.3 での切り替えがまだ安定していません。スタック完了から **6 〜 10 分** を見込んでください。それまでの `PENDING` は壊れているのではなく正常です。

じっと見ているのではなく、時間を活用してください。[Path A.5](../05-summary/) にざっと目を通してこの先の流れを把握するか、Code Editor で `travel-agent-strands/runtime/main.py` を開いて Coordinator が Runtime にどう公開されているかを見てください。その後、コマンドを再実行します。
:::

:::alert{type="info" header="学習: 一部のセッションが決して採点されない理由"}
Transaction Search は、取り込みが稼働した時点から先のスパンのみを `aws/spans` ロググループにインデックス化します。それ以前に作成されたセッションはインデックス化されないため、モジュール 2 で採点できず、エラーも報告されません。後になって結果のロググループが空であることに気づき、理由を突き止める必要が生じるだけです。

Path A.2 のスモークテストは、そうしたセッションの 1 つです。エージェントが動作することを証明しましたが、評価には現れません。これは想定どおりです。
:::

## 4.2: いくつかクエリを実行する

```bash
cd /workshop/edd-workshop/travel-agent-strands
agentcore invoke "What attractions are open on weekends in Luminara?"
agentcore invoke "Plan a 1-day trip starting Friday focusing on culture"
agentcore invoke "Suggest a dinner restaurant near the Royal Palace"
```

各呼び出しが Runtime 内に別々のセッションを作成します。

## 4.3: コンソールで確認する

ここが成果の見せ場で、どんなコマンドよりもコンソールのほうがよく見えます。**CloudWatch** を開き、左ナビゲーションで **GenAI Observability**、次に **Bedrock AgentCore** を開きます ([直接リンク](https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#gen-ai-observability/agent-core))。

モジュール 0 で空の「変更前」の状態だったダッシュボードに、実際のセッション数とトレース数を伴ってエージェントが一覧表示されるはずです。

![期待される結果: 呼び出し後に値が入った GenAI Observability ダッシュボード。エージェントのセッション数、トレース数、トークン数が表示されている](/static/images/module-1/1a-dashboard-populated.png)

:::alert{type="info" header="メトリクスのタイルがトレース一覧より少ない呼び出し数を表示する場合"}
上部のタイルは OTEL メトリクスから作られており、トレースのインデックスより遅い間隔で集計されます。**All traces** タブがすでに 3 件を表示している一方でタイルが 2 件の場合、それはデータの欠落ではなく集計の遅れです。1 分ほど待ってください。トレース一覧が真実の情報源です。
:::

トレースを掘り下げると、呼び出しごとに 1 つのトレースが見えるはずです。

![期待される結果: 呼び出しごとに 1 つのトレースが並ぶトレース一覧。各トレースにスパン数が表示されている](/static/images/module-1/1a-traces-list.png)

任意のトレースを開くと、完全なウォーターフォールが表示されます。開いた時点では **`Agent spans = true`** のクイックフィルターが適用されているため、ツリーは `invoke_agent` から始まります。**Clear filters** をクリックすると、Strands のサイドカーが捕捉したすべてが見えます。ルートに `POST /invocations`、続いて `invoke_agent → execute_event_loop_cycle → chat`、そしてツールのスパン (`query_sites → plan_route → suggest_dining`) です。

![1 回の呼び出しのトレース詳細。ボックス 1: スパンのツリー、つまりエージェントのトラジェクトリ。ボックス 2: リソース属性内の service.name、モジュール 2 がフィルターに使う結合キー](/static/images/module-1/1a-trace-waterfall.png)

**このスパンのツリーがトラジェクトリです。** モジュール 2 のジャッジが読むものであり、モジュール 3 がテストする対象です。これが見えていれば、モジュール 1 は役割を果たしました。

コンソールはトレース詳細ページで、同じものをラベル付きの **Trajectory** グラフとしても描画します。今のうちに見ておく価値があります。そのグラフはまさに、モジュール 3 が「エージェントは `plan_route` より前に `query_sites` を呼んだか」と問うときに採点する対象そのものです。

## 4.4: レコードの形状を確認する

コンソールはデータが届いたことを証明します。次の確認は、ダッシュボードには表示されない、モジュール 2 が依存する *形状* を持っていることを確かめます。

```bash
cd /workshop/edd-workshop
./scripts/verify-telemetry.sh
```

すべてのチェックが成功するはずで、スクリプトは `4 passed, 0 failed` のようなサマリー行で終わります (セクション 2 は独自に 2 つのアサーションを行うため、件数がセクション数より多くなります)。出力される `service.name`、レコードのスコープ、相関キー、名前別のスパン数が表示されます。

:::alert{type="info" header="任意: スクリプトが検証している内容"}
Code Editor で `scripts/verify-telemetry.sh` を開いて読んでください。トレースの保存先が稼働していること、エージェントのロググループに `input` と `output` の両方のボディを持つレコードがあること、レコード内の `service.name` が使用中のものと一致すること、そしてそのサービスのスパンが `aws/spans` に存在することを確認します。

3 番目のチェックには存在意義があります。モジュール 2 はレコードの **内部** の値でフィルターするため、不一致があるとスコアがゼロになり、エラーも出ません。スクリプトが両者を比較するので、モジュール 2 ではなく今の時点で気づけます。
:::

:::alert{type="warning" header="チェック 3 が no spans と表示する場合"}
エクスポートに約 30 秒の猶予を与えて再実行してください。バッチ処理されています。それでも空のままなら、取り込みの準備完了より前に呼び出しが行われました。チェック 1 が `ACTIVE` になった今、もう一度呼び出してから再実行してください。過去のセッションは遡って取り込まれません。
:::

:::alert{type="info" header="学習: Strands に `session.id` 属性がない理由"}
Strands は明示的な `session.id` 属性ではなく `traceId` を使ってセッションを相関付けます。モジュール 2 の評価器はトレースで結合するため、データはすでに評価可能な状態です。`session.id` を探して見つからなくても、何も問題はありません。
:::

## 可観測性はこれで完成

ログレコードはエージェントのロググループに届き、スパンは `aws/spans` に到達し、ダッシュボードにトラジェクトリが表示されます。まだ欠けている唯一のものは採点です。エージェントの **Evaluations** タブには *「No evaluation configurations to display in the selected time range」* と表示されます。まだ評価器が接続されていないからです。モジュール 2 でこれを解決します。

今捕捉したツール呼び出し、引数、応答は、まさに LLM ジャッジが読むものです。トラジェクトリが豊かであるほど、スコアは実用的になります。
