---
title: "2.4 GenAI Observability ダッシュボードの探索"
weight: 40
---

## GenAI Observability コンソールを開く

最も確実な方法は左ナビゲーションです (ディープリンクの URL は CloudWatch のホームページに戻されることがあります)。AWS コンソールで **CloudWatch** を開き、左ナビゲーションで **GenAI Observability → Bedrock AgentCore** を展開します。

直接の URL は次のとおりです。

```
https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#gen-ai-observability/agent-core
```

:::alert{type="info" header="CloudWatch の概要ページに着いてしまいましたか"}
古い `#gen-ai-observability:tab=runtimes` のリンク (および **クロスアカウント / 集中モニタリング** のアカウントでの一部のディープリンク) は CloudWatch のホームページにリダイレクトします。その場合は URL を無視して左ナビゲーションを使ってください: **GenAI Observability → Bedrock AgentCore**。目的のタブのラベルは「Runtimes」ではなく **Bedrock AgentCore** です。
:::

## ダッシュボードを見ていく

### 1. エージェントの概要

エージェントが一覧表示されます (例: `travel-agent-edd-workshop`)。クリックしてエージェントの詳細ビューを開きます。

![AgentCore Observability Console](/static/images/module-2/agentcore-observability-dashboard.png)

**期待される結果: 評価器が登録され有効になっています。** セッションを掘り下げる前に、Online Evaluation Config が **ACTIVE** と表示されていることを確認してください。これはステップ 2.2 でデプロイした設定で、自動採点を駆動しているものです。

![期待される結果: ACTIVE として一覧表示された Online Evaluation Config](/static/images/module-2/eval-configs-active.png)

### 2. エージェントのダッシュボード

エージェントの **Overview** タブには、次の順で表示されます。

- **Top deltas in evaluator scores**: スコアの推移。最初のスコアが届くまでは空です
- **Top spans by errors**: 各スパン名と、そのトレース数、トークン、エラー、`Avg. span latency (ms)`
- 時系列の **Sessions, invocations and errors**
- **FM token usage**、続いて **Cost usage and trends**、**Model cost ($)**、**Avg cost per trace ($)**
- **Endpoint details**

ここに p50/p90/p99 のレイテンシウィジェットはありません。レイテンシはエラーテーブルではスパン単位、**OTEL sessions** タブではセッション単位です。他のタブは **Evaluations**、**OTEL sessions**、**Traces**、**Spans** です。

:::alert{type="info" header="低ボリュームではスコアのウィジェットが疎になることがあります"}
呼び出しが 3 回だけの場合、「Top deltas in evaluator scores」ウィジェットの表示データは最小限になることがあります。時間をかけてセッションが蓄積すると、このウィジェットはより有用になります。

設定が `ACTIVE` なのにエージェント単位の **Evaluations** ウィジェットが **「No evaluation configurations to display」** と表示することがあっても、失敗と考えないでください。低ボリュームかつ短い時間範囲では、このウィジェットは遅れることがあります。採点が実際に行われたかどうかの真実の情報源は、評価結果の **ロググループ** (ステップ 2.3) です。
:::

### 3. Evaluations タブ

**Evaluations** タブをクリックします。開くと **Evaluation configuration metrics** テーブルが表示され、`Builtin.Helpfulness` が `Errors` と `Throttles` と並んで `Results count` を示します。この件数が、採点が実際に行われていることの最も手早い確認になります。

その下で結果は 3 つのバケットに分かれ、埋まるのは真ん中だけです。スコアは **トレース** の評価として届くため、**Session evaluations** ではなく **Trace evaluations** を読んでください。6 セッションが採点されたアカウントでの実測です。

```
Session evaluations (0)
Trace evaluations (6)
Span evaluations (0)
```

ゼロ 2 つと実数 1 つが正常な形であり、データ欠落のバグではありません。`Builtin.Helpfulness` がトレースレベルの評価器だからです。ご自身の数値は、これまでに採点されたセッション数です。モジュール 1 の直後にここへ来た場合はモジュール 1 の実行も含まれるため (ステップ 2.3 のボックスを参照)、そのページの 3 回の呼び出しと等しくなるとは考えないでください。

### 4. OTEL sessions タブ

**OTEL sessions** タブをクリックすると、個々のセッションが見えます。列は次のとおりです。

- Session ID
- Traces
- Total tokens
- Token cost
- Errors
- Throttles
- Avg. trace latency (ms)

ここに **ない** ものにも注目してください。セッション単位の評価スコアの列はなく、タイムスタンプや継続時間の列もありません。セッションをクリックするとそのトレースと会話全体を掘り下げられますが、ジャッジのスコアと説明には **Evaluations** タブか、ステップ 2.3 の評価結果ロググループを使ってください。

### 5. ロググループ内の評価結果

ジャッジの説明は評価結果のロググループにのみ存在するため、全文を読むのはそこです。

![Evaluation Results](/static/images/module-2/evaluation-results-log-events.png)

このビューでできること:
- 低いスコアだったセッションを見つけ、理由を調査する
- 時間経過に伴うスコアの推移を追う (新しいデプロイは品質を改善しているか)
- 異なる時間帯のスコアを比較する

## 見ているもの

ダッシュボードは、接続したすべてを 1 か所に集めます。

| データソース | 出どころ | 示すもの |
|---|---|---|
| トレース | モジュール 1 の OTEL 計測 | レイテンシ、ツール呼び出し、スパンの階層 |
| ログイベント | モジュール 1 の `invoke_agent` ログレコード | セッションの記録 (入力 + 出力) |
| 評価スコア | モジュール 2 の評価器 (このモジュール) | セッションごとの自動品質スコア |

3 つの面はすべて `service.name` とセッション ID で結合されます。Path B では、アダプターが両方を設定します。Path A では、サイドカーが `service.name` を刻印し、Runtime がセッション ID を割り当てます。これが、スパンが `session.id` 属性を持たないのにコンソールがセッションを一覧できる理由です (Path A.4 のボックス)。

## 重要なポイント

評価のコードを 1 行も書かずに、**継続的で自動的な品質モニタリング** が手に入りました。エージェントが処理するすべてのセッションが採点され、1 つのダッシュボードに表示されます。品質が上向きか下向きかを知るために、人間が会話ログを読む必要はありません。
