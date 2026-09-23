---
title: "Path A: AgentCore Runtime 上の Strands"
weight: 10
---

これは **すべてマネージドのパス** です。AgentCore CLI (`@aws/agentcore`) を使って Strands の Python エージェントを AgentCore Runtime にデプロイします。Runtime のサイドカーが代わりに OTEL のトレースとログを出力します。あなたの作業は、エージェントを `agentcore deploy` し、正しい `service.name` で可観測性の CFN をデプロイすることだけです。

## これから構築するもの: 可観測性

このパスを終えると、エージェントのすべての呼び出しが次のものを生成します。

- **X-Ray のトレース**: Runtime のサイドカーが自動的にエクスポート
- **CloudWatch のログイベント**: 正規の `invoke_agent` レコード (サイドカーが出力)
- **GenAI Observability ダッシュボードのスパン**: エージェントの `service.name` の下に表示

評価スコアはまだありません。モジュール 2 で、この土台の上に自動 LLM ジャッジの採点を追加します。

## やること

1. **Path A.1 これから構築するもの**: アーキテクチャと、本来自分で書くことになる OTEL の配線を Runtime のサイドカーがどう置き換えるかを見ます。
2. **Path A.2 エージェントのデプロイ**: AgentCore CLI で `agentcore deploy`。約 5 分。自動生成される `service.name` を確認します。
3. **Path A.3 `agentcore-observability.yaml` のデプロイ**: 可観測性インフラ (Transaction Search + ロググループ + インデックスポリシー) をデプロイします。約 3 分。
4. **Path A.4 呼び出しと確認**: エージェントに Luminara に関する質問をし、X-Ray のトレースと CloudWatch のログイベントを確認します。約 5 分。
5. **Path A.5 振り返りと次の内容**: 接続したものと、Path B との比較。

## このパスが適している場合

- すでに Strands で構築している。
- AWS マネージドな可観測性の要件がある (コンプライアンス、集中モニタリング)。
- エージェント用に長時間稼働するコンピュート層を運用したくない。

エージェントが Strands で構築されていない場合は、代わりに **[Path B](../path-b-any-framework/)** を使ってください。

## 所要時間

約 20 分。

::children
