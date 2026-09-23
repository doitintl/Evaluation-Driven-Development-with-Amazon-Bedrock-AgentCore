---
title: "Path A.1 これから構築するもの"
weight: 10
---

## これから構築するもの

Strands の Python トラベルエージェント (`travel-agent-strands/`) を **Amazon Bedrock AgentCore Runtime** にデプロイします。Runtime に組み込まれた OTEL サイドカーが、トレースと正規の `invoke_agent` ログイベントを自動的に出力します。その後、すべての呼び出しを採点するために eval+obs の CloudFormation スタックをデプロイします。

![Path A: agentcore deploy が Strands エージェントをマネージドな AgentCore Runtime にパッケージし、注入された OTEL サイドカーがスパンを Observability へ、さらに Online Evaluation へエクスポートします。テレメトリのコードは一切書きません。](/static/images/diagrams/path-a-architecture.png)

## これが最もシンプルなパスである理由

Runtime の OTEL サイドカーが、Path B で必要な接続作業のすべてを置き換えます。

- サイドカーが `invoke_agent` ログレコードを、正しい非対称のボディ形状で出力します。追加作業なしで。
- セッション相関キーとして `traceId` を自動的に伝播します。
- すべてのレコードに `service.name = <agentName>.<endpoint>` を刻印します (ドット連結、ランタイム ID は除外)。ロググループ側はランタイム ID を保持するため、2 つの文字列は異なります。Path A.2 で両方を取得します。
- SigV4 で署名し、OTLP を AWS のエンドポイントにエクスポートします。

**OTEL のコードを一切書かず、OTEL の環境変数も一切設定しません。** あなたの責任は次の 3 点だけです。

1. `agentcore deploy`: AgentCore CLI でエージェントをデプロイする。
2. 自動生成される **両方の** 名前を CloudWatch から取得する (Path A.2 が代行します)。
3. 名前の **ロググループ形式** (`RUNTIME_LOG_SUFFIX`、ランタイム ID を保持するほう) を `ServiceName` パラメーターとして `cfn/agentcore-observability.yaml` をデプロイする。ドット連結で出力される `service.name` は別の値であり、モジュール 2 で登場します。

これがこのパスのすべてです。

## なぜ `service.name` はデプロイ前ではなくデプロイ後に判明するのか

AgentCore Runtime はランタイム ID に基づいて `service.name` を自動生成し、そのランタイム ID は `agentcore deploy` が成功した *後* にしか存在しません。そのためこの異例の順序になります。エージェントをデプロイ (Path A.2) してから可観測性の CFN をデプロイ (Path A.3) し、その逆ではありません (Path B は先に可観測性をデプロイし、その後エージェントを計測します)。

この鶏と卵の問題を回避するため、`agentcore.json` に独自の `service.name` をハードコードするチームもあります。それでも問題ありません。ここでは AWS のドキュメントの手順と一致するため、自動生成のデフォルトを採用しました。

## すでにディスク上にあるもの

```bash
travel-agent-strands/
├── README.md
├── requirements.txt
├── main.py                       # local CLI (not used by Runtime)
├── agentcore/
│   └── agentcore.json            # AgentCore CLI deploy spec — read this in Path A.2
│                                 # (aws-targets.json is generated on-box during deploy)
├── runtime/
│   └── main.py                   # BedrockAgentCoreApp wrapper Runtime invokes
└── src/                          # the Strands Coordinator + 3 tools
```

ステップ 02: エージェントをデプロイします。ステップ 03: 評価の CFN をデプロイします。ステップ 04: 呼び出して確認します。
