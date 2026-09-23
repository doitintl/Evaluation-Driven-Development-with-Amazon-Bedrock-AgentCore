---
title: "2.3 トラフィックの生成とスコアの確認"
weight: 30
---

**シナリオ。** 評価器はデプロイ済みですが、まだ 1 つもセッションを見ておらず、採点する対象がありません。このステップで実際のトラフィックを作り、その後スコアを読み戻します。ここからワークショップは配線の話ではなくなります。**これ以降は、配線が動くことの確認ではなく、エージェントの品質に関する判定を読んでいきます。**

## トラフィックを生成する

評価器が採点できるセッションを作るため、エージェントを 3 回呼び出します。モジュール 1 で選んだパスに合う呼び出し方法を使ってください。

:::alert{type="warning" header="まず Transaction Search が ACTIVE であることを確認してください"}
トレースの保存先がまだ `PENDING` の間に作成されたセッションはインデックス化されないため、決して採点されず、以下の待ち時間も永遠に終わりません。

```bash
aws xray get-trace-segment-destination --region us-east-1 --query 'Status' --output text
```

これが `ACTIVE` と表示されてから進んでください。
:::

### Path B: 任意のフレームワーク (このワークショップの pi-mono OpenInference アダプター)

Path B で構築したのと同じ OpenInference アダプターを実行します。評価器が直接採点するトラジェクトリのスパンを出力するので、追加で有効にするものはありません。

```bash
cd /workshop/edd-workshop/openinference-aws-adapter
USER_QUERY="What attractions are open on weekends in Luminara?" npm start
USER_QUERY="Plan a 2-day trip focused on history, arriving Monday"   npm start
USER_QUERY="Suggest a dinner restaurant near the Royal Palace"       npm start
```

➡️ **あなたのフレームワークの場合:** 計測済みのエージェントを普段どおりの方法で呼び出してください。重要なのは、各呼び出しが `/aws/bedrock-agentcore/runtimes/${SERVICE_NAME}` の下に OpenInference のスパンを出力することだけです。

### Path A: AgentCore Runtime 上の Strands

```bash
cd /workshop/edd-workshop/travel-agent-strands
agentcore invoke "What attractions are open on weekends in Luminara?"
agentcore invoke "Plan a 2-day trip focused on history, arriving Monday"
agentcore invoke "Suggest a dinner restaurant near the Royal Palace"
```

## スコアを待つ

最後の呼び出しの後、評価パイプラインには時間が必要です。

1. **セッションのアイドルタイムアウト** (5 分): AgentCore がセッションのアイドル化を待ちます。
2. **ジャッジの採点** (約 5-10 分): LLM ジャッジが記録を読んで採点します。

**合計の待ち時間: 最大 20-25 分を見込んでください。** 実際には 10-15 分の範囲に収まることが多いものの、ジャッジのキューの混雑によりそれを大きく超えることもあります。15 分経って何も現れなくても、必ずしも壊れているわけではありません。失敗と決めつけず、数分おきにポーリングを続けてください。25 分を過ぎて何もない場合にのみ、トラブルシューティング (下記) を始めてください。

:::alert{type="info" header="待っている間に"}
この時間を有効に使ってください。

- ステップ 2.1 のアーキテクチャ図を読み返し、メンタルモデルを固めます。
- CloudWatch コンソールでモジュール 1 の X-Ray トレースを探索します: **CloudWatch > X-Ray traces > Traces**。
- エージェントのロググループを参照し、エージェントが出力した生のスパンを見ます。
- ステップ 2.4 (ダッシュボードの探索) を先読みし、スコアが届いたときに何を見るべきか把握します。
:::

## スコアが届いたことを確認する

待ち時間の後、評価用ロググループでスコアを確認します。

```bash
cd /workshop/edd-workshop
./scripts/read-eval-scores.sh
```

:::alert{type="warning" header="待った後も結果が空ですか"}
スクリプトは何も表示しないのではなく、その旨を明示します。25 分経ってもスコアがないと報告される場合は、下のトラブルシューティングの手順を進めてください。

これらのロググループに対して独自のクエリを書く場合は、`--limit` ではなく `--max-items` を使ってください。生の `--limit` API パラメーターは、実際にスコアが存在していても黙って 0 件のイベントを返すことがあります。スクリプトがこの理由で `--max-items` を使っています。
:::

## 期待される出力

次のものを含む JSON レコードが見えるはずです。

- `gen_ai.evaluation.score.value`: 0.0 から 1.0 の浮動小数点数
- `gen_ai.evaluation.score.label`: コンソールに表示される表現。たとえば `Above And Beyond`
- `gen_ai.evaluation.explanation`: そのスコアに対するジャッジの理由付け
- `gen_ai.evaluation.name`: どの評価器がスコアを生成したか。ここでは `Builtin.Helpfulness`
- `session.id`: 呼び出し時のセッション ID と一致するもの

実際のレコードから抜粋した例:

```json
{
  "gen_ai.evaluation.name": "Builtin.Helpfulness",
  "gen_ai.evaluation.score.value": 1.0,
  "gen_ai.evaluation.score.label": "Above And Beyond",
  "gen_ai.evaluation.explanation": "The user requested a 1-day trip starting Friday focusing on culture. The assistant's response delivers a comprehensive, well-organized itinerary that ...",
  "session.id": "bd8734a9-5221-42de-bfd0-ff8719f5e45e",
  "gen_ai.response.id": "6a86c659232c43303a2a72f8295d34b8"
}
```

:::alert{type="warning" header="独自のクエリを書く場合: 2 つのキー名は予想とは異なります"}
レコードはセッションを `session.id` と呼び、`gen_ai.session.id` では **ありません**。また評価器を `gen_ai.evaluation.name` と呼び、`gen_ai.evaluation.evaluator_id` では **ありません**。実際のレコードでの実測では、これらの長い綴りを grep しても何も返りません。

`read-eval-scores.sh` は `gen_ai.evaluation.name` を読み、フォールバックとして `evaluator_id` を、`session.id` を読み、フォールバックとして `gen_ai.session.id` を使うため、サービスがどちらの綴りを出力してもスクリプトは動作し続けます。誤ったキーで手書きしたクエリは、エラーなしで 0 行を返し、これは「まだスコアがない」ようにしか見えません。
:::

:::alert{type="info" header="今送った 3 セッションより多くのレコードがありますか"}
想定どおりで、理解しておく価値があります。評価器は、設定が `ACTIVE` になった後に完了する、エージェントのロググループ内のすべてのセッションを採点します。モジュール 1 の呼び出しも同じロググループにあります。モジュール 1 からここへ直接進んだアカウントでの実測では、モジュール 1 の 3 セッションは実行から約 13 分後に採点され、このページの 3 セッションは約 15 分後に採点され、その結果 `read-eval-scores.sh` は 3 件ではなく **6 score(s) across 1 evaluator(s)** と報告しました。

設定が存在する前にかなり以前に終わっていたセッションは、まったく取り上げられません。そのためモジュール間で長い休憩を取ったアカウントでは、このページの 3 件だけが見えます。どちらの件数も正しいです。合計ではなく ID で照合してください。
:::

**期待される結果: コンソールに実際のスコア。** CloudWatch コンソールでは、評価結果のロググループに、採点されたセッションごとに 1 つの `gen_ai.evaluation.result` レコードが表示されます。それぞれが `Builtin.Helpfulness` のスコアとジャッジの説明を持ちます。ここでは 3 セッションすべてが 1.0 (「Above And Beyond」) を獲得しています。

![評価結果のロググループ。ボックス 1: 採点されたセッションごとに 1 つの gen_ai.evaluation.result レコード。それぞれが Builtin.Helpfulness のスコアとジャッジの説明を持つ](/static/images/module-2/eval-scores-expected.png)

任意のレコードを展開すると、ジャッジの自由記述による完全な説明が読めます。これがスコアを単なる数値ではなく実用的なものにします。

![期待される結果: 展開されたスコアレコード。LLM ジャッジが、そのセッションをなぜそう採点したのかの完全な説明を表示している](/static/images/module-2/eval-score-explanation-expanded.png)

このようなセッション単位のスコアと説明が見えていれば、Online Evaluator はエンドツーエンドで機能しています。

**ここで 1 つのレコードを解釈してください。存在の確認だけで終わらせないこと。** 任意のスコアレコードを選び、次の 3 つの問いに答えてください (これがテレメトリを *持っている* ことと *使っている* ことの違いです)。

1. **因果関係を追う:** レコード内の `session.id` を見つけ、上の呼び出しのターミナル出力で同じセッション ID を見つけます。その結び付き、つまり *あなたの* CLI 呼び出し → セッション → ジャッジのスコアが、オンライン評価パイプライン全体を 1 組の ID で表しています。照合 *できる* ものが見つかるまでレコードを見ていってください。一部は今送った 3 件ではなくモジュール 1 の実行に属している可能性があります (上のボックスが理由を説明しています)。自分のどの実行にも紐付けられないレコードは、そのスコアが自分の思っているものを測っていないことを告げています。
2. **説明を記録と照らし合わせて検証する:** ジャッジの説明は、エージェントが実際に述べたことを引用していますか。ジャッジは測定器であり、測定器には校正が必要です。いくつかの説明を生の応答と照らし合わせて読むことが、実務者が数値を信頼する前にジャッジを検証する方法です。説明が一般的なもの (「応答は有用で詳細だった」) なら、それは *スタイル* を採点しています。具体的なもの (「日曜については Old Quarter Walking Tour を正しく除外した」) を引用していれば、*実質* を採点しています。
3. **低いスコアならどう見えたかを問う:** これらの Grand Museum に関するクエリが高得点なのは、エージェントが正しいデータとプロンプトを持っているからです。このジャッジが 0.3 を付けるのはどんなユーザークエリで、その *説明* は失敗を再現するのに十分な情報を与えてくれるでしょうか。その答えを覚えておいてください。モジュール 4 では、まさにそうした低スコアのセッションを掘り出して新しいテストケースを作ります。

:::alert{type="info" header="ここでどこも「Above And Beyond」になるのが想定どおりな理由と、本番ではそれが何を意味するか"}
この統制された環境では、すべてのセッションが 1.0 になるのが正しいです。健全なエージェントに、十分に裏付けのある易しいクエリを送ったからです。本番環境では、満点の壁は祝うべきものではなく、ジャッジを確認すべきシグナルです。トラフィックが実際のユーザーのニーズより易しいか、評価器が甘すぎるかのどちらかです。有用なオンライン評価器は、低いほうに裾を持つ分布を示します。その裾こそエンジニアリングの仕事がある場所です (そしてモジュール 4 が狩りに出る場所です)。
:::

## トラブルシューティング

25 分経ってもスコアが現れない場合:

1. **エージェントのロググループにイベントがあるか確認する**: 評価器は、そもそもログに残っていないセッションを採点できません。
   ```bash
   aws logs filter-log-events \
     --log-group-name "/aws/bedrock-agentcore/runtimes/${SERVICE_NAME}" \
     --max-items 3 \
     --query 'events[*].message' --output text | head -50
   ```

2. **Online Evaluation Config のステータスを確認する**: `ACTIVE` である必要があります。
   ```bash
   aws bedrock-agentcore-control list-online-evaluation-configs \
     --query 'onlineEvaluationConfigs[*].{name:onlineEvaluationConfigName, status:status}' \
     --output table
   ```
   (このサブコマンドには最近の **AWS CLI v2** が必要です。`Invalid choice` と報告される場合は、モジュール 0 のセットアップにあるバージョンの注記を参照してください。)

3. **`serviceNames` のフィルターが、レコードが実際に持っている値と一致するか確認する。** 不一致の場合、評価器は正しいロググループを監視しながらその中のどのレコードにも一致しないため、エラーは出ず、何も採点されません。
   ```bash
   # what the config filters on
   CFG_ID=$(aws bedrock-agentcore-control list-online-evaluation-configs \
     --region us-east-1 \
     --query 'onlineEvaluationConfigs[0].onlineEvaluationConfigId' --output text)

   aws bedrock-agentcore-control get-online-evaluation-config \
     --online-evaluation-config-id "$CFG_ID" --region us-east-1 \
     --query 'dataSourceConfig.cloudWatchLogs.[logGroupNames,serviceNames]' --output json
   ```
   `serviceNames` の値は、出力される値と **完全に** 一致する必要があります。Path A ではこれらは 2 つの異なる文字列です (ロググループはランタイム ID を保持し、出力される名前はドット連結です)。だからこそ Path A はステップ 2.2 で `ServiceName` と `EmittedServiceName` の両方を渡します。
