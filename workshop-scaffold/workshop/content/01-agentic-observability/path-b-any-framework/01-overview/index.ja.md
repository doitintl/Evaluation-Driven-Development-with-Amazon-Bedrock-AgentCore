---
title: "Path B.1 概要"
weight: 10
---

## これから構築するもの

エージェントのライフサイクルイベントを購読し、3 種類のスパンを AWS に出力する、約 200 行の **OpenInference アダプター** です。

| スパン種別 | 単位 | 保持する情報 |
|---|---|---|
| `AGENT` | 呼び出しごとに 1 つ | ユーザーのクエリと最終的な回答 |
| `LLM` | モデル推論ごと | モデル名、トークン数、参照したメッセージ |
| `TOOL` | ツール実行ごと | ツール名、引数、結果 |

エージェントのロジックは **何も** 変更しません。アダプターは外側から観測し、スパンを SigV4 で署名して X-Ray の OTLP エンドポイントに送ります。

:::alert{type="success" header="持ち帰るべき 1 つの考え: 1 つのスコープが 2 つの役割を果たす"}
**ダッシュボード** 向けに出力するスパンは、モジュール 2 で AgentCore Evaluation が **採点する** スパンとまったく同じです。2 つ目のエクスポートも、フレームワークの偽装も、別個のログイベントもありません。

だからこそ、このパスは約 45 分をかける価値があります。一度計測すれば、デバッグと自動採点の両方が機能します。モジュール 4 でコーディングエージェントが 4 つ目のツールを追加すると、その呼び出しは `TOOL` スパンになり、アダプターを変更せずに自動的に採点されます。
:::

## 素の OpenTelemetry では不十分な理由

標準 OTEL の `gen_ai.*` 名前空間にはエージェント用とツール用のスパンがありますが、**個々のモデル推論用のスパンはありません**。そのため、平坦な 2 階層のツリーになります。

```
invoke_agent                      ← standard OTEL sees this
├── execute_tool query_sites      ← and these
├── execute_tool plan_route
└── execute_tool suggest_dining
```

エージェントが 3 つのツールを呼んだ *こと* は見えます。しかし *どのモデル呼び出しがそう決めたのか*、何を見ていたのか、いくらかかったのかは見えません。

OpenInference は、欠けていた中間層を追加します。

```
invoke_agent                    (AGENT, 41.70s)
├── llm-call-2                  (LLM, 0.90s, 3/77 tokens)      → decides to call query_sites
├── execute_tool query_sites    (TOOL, 0.01s)
├── llm-call-3                  (LLM, 0.85s, 1911/105)         → decides to call plan_route
├── execute_tool plan_route     (TOOL, 0.01s)
├── llm-call-4 to llm-call-8    (LLM, one per model turn)      → each decides the next call
├── execute_tool suggest_dining (TOOL, 0.00s)
└── llm-call-9                  (LLM, 19.53s, 5809/1199)       → final synthesis
```

これでエージェントの推論がクエリ可能になります。この実行ではモデル呼び出しが 9 回、遅いのは合成の呼び出しで、ツール選択の呼び出しは比較的安価です。(番号が 2 から始まるのは、最初のスパンがご自身のプロンプトに属するためです。Path B.4 で説明します。)

Path B.4 を終えると CloudWatch ではこう見えます。計測されたエージェントが、セッション数とトレース数とともに一覧表示されます。

![Path B 後の CloudWatch GenAI Observability ダッシュボード。計測されたエージェントがセッション数とトレース数とともに表示されている](/static/images/1f-genai-dashboard.png)

:::alert{type="info" header="任意: 標準 OTEL と OpenInference の完全な比較"}
| 観点 | 標準 OTEL (`gen_ai.*`) | OpenInference |
|---|---|---|
| スパンの階層 | 2 階層 | 3 階層 (`AGENT` → `LLM` → `TOOL`) |
| LLM 呼び出しの可視性 | なし、不透明 | あり、1 呼び出しに 1 スパン |
| トークンの追跡 | なし | `llm.token_count.prompt` / `.completion` / `.total` |
| モデルの帰属 | なし | 呼び出しごとの `llm.model_name` |
| メッセージ内容 | 最終的な入出力のみ | 呼び出しごとの `llm.input_messages` + `llm.output_messages` |
| ポータビリティ | AWS 固有 | Arize Phoenix、Langfuse でも機能 |

[OpenInference](https://github.com/Arize-ai/openinference) はオープンなセマンティック規約の標準なので、同じ計測が複数のバックエンドで機能します。AWS は [AgentCore Observability のドキュメント](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html) で、Strands 以外のフレームワーク向けにサポートされる計測ライブラリとして、Openllmetry、OpenLit、Traceloop と並べてこれを挙げています。
:::

:::alert{type="info" header="任意: AgentCore がこのスコープをネイティブに採点する証拠"}
オンデマンドの Evaluate API で検証済みです。`openinference.instrumentation.pi-mono` の下で出力された pi-mono のセッションは、Google ADK のような一級のフレームワークと同じように `TrajectoryInOrderMatch`、`ToolParameterAccuracy`、`ToolSelectionAccuracy`、`Faithfulness` で採点されます。評価器はツール名、引数、結果、最終的な回答をスパンから直接読み取ります。
:::

:::alert{type="info" header="仕組み: このワークショップは pi-mono を使いますが、手法はフレームワークに依存しません"}
サンプルエージェントは **pi-mono** (TypeScript) なので、以下のコマンドはすべて具体的でコピー & ペーストできます。アダプターのなかで pi-mono 固有なのは 1 行だけ、エージェントのインポート部分です。各ステップには、LangGraph、CrewAI、独自エージェントで何が変わるかを正確に示す **➡️ あなたのフレームワークの場合** の注記が付いています。
:::

## 始める前に必要なもの

- Path B.2 の完了 (Transaction Search が有効、ロググループが作成済み)
- Code Editor にすでにクローンされている `travel-agent` のコード
- Node.js 20+ (プリインストール済み)

**次: [Path B.2 可観測性インフラのデプロイ](../02-deploy-obs-cfn/)。**
