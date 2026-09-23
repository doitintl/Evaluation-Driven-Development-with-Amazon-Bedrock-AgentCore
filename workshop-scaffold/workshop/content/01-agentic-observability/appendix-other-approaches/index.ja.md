---
title: "付録: その他の計測アプローチ"
weight: 90
---

モジュール 1 では 2 つのパスを提供します。**Path A** (AgentCore Runtime 上の Strands、テレメトリは追加作業なし) と **Path B** (OpenInference アダプター経由のその他すべてのフレームワーク) です。使うべきなのはこの 2 つです。

この付録は **参考情報のみ** で、ワークショップの完了には必要ありません。以前のバージョンのワークショップが独立した選択肢として教えていた 2 つの代替的な接続方法を、その制約を持つチームのために残しています。

---

## A. 素の EC2 / ECS 上の Strands (AgentCore Runtime なし)

Strands で構築しているものの AgentCore Runtime にデプロイできない場合 (自前の EC2、ECS、k8s を運用している場合)、アダプターは一切不要です。Strands に組み込まれた `strands.telemetry` が、正規の AgentCore レコードをネイティブに出力します。環境変数で OpenTelemetry を AWS のエンドポイントに向け、`opentelemetry-instrument` 配下で起動するだけです。

接続作業は OTEL 変数の `.env` です (ADOT を有効化し、OTLP のエンドポイントを設定し、ロググループにルーティングし、`service.name` を設定します)。

```bash
# ADOT activation
export OTEL_PYTHON_DISTRO=aws_distro
export OTEL_PYTHON_CONFIGURATOR=aws_configurator
export OTEL_TRACES_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf

# AWS OTLP endpoints
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=https://xray.us-east-1.amazonaws.com/v1/traces
export OTEL_EXPORTER_OTLP_LOGS_ENDPOINT=https://logs.us-east-1.amazonaws.com/v1/logs

# Route log events to the agent's runtime log group
export OTEL_EXPORTER_OTLP_LOGS_HEADERS=x-aws-log-group=/aws/bedrock-agentcore/runtimes/travel-agent-strands-edd-workshop,x-aws-log-stream=runtime-logs

# Identify the agent
export OTEL_RESOURCE_ATTRIBUTES=service.name=travel-agent-strands-edd-workshop
export AGENT_OBSERVABILITY_ENABLED=true
```

その後、計測ラッパー経由でエージェントを実行します。

```bash
opentelemetry-instrument python main.py "Plan a 2-day trip focused on history, arriving Monday"
```

結果は Path A のテレメトリと同一です。同じロググループ、同じレコードで、マネージドな Runtime がないだけです。トレードオフは、コンピュートを自分で運用することです。

---

## B. ログイベントの契約はどう機能するのか (BYO ブリッジを原理から)

Path B の OpenInference アダプターは、Strands 以外のエージェントを計測する本番向けの方法です。ただし、そのアダプターが内部で実際に何を満たしているのか、つまり AgentCore が期待する **ログイベントの契約** を理解しておく価値があります。

歴史的には、AgentCore Evaluation が OpenInference のスコープファミリーをサポートする前、Strands 以外のエージェントは Strands を *偽装* する必要がありました。`strands.telemetry.tracer` の下で `invoke_agent` スパンを出力し、**さらに** 特定の「非対称ボディ」形状を持つ対応する CloudWatch ログイベントを出力するのです (入力はコンテンツのリスト、出力はメッセージ文字列)。

```jsonc
{
  "input":  { "messages": [{ "content": { "content": "[{\"text\":\"<user query>\"}]" }, "role": "user" }] },
  "output": { "messages": [{ "content": { "message": "<agent response>", "finish_reason": "end_turn" }, "role": "assistant" }] }
}
```

これはもう必要ありません。AgentCore Evaluation は現在、OpenInference の **スパン** からトラジェクトリをネイティブに読み取ります (これが Path B が依拠しているもので、動作が検証済みです)。ただし非対称ボディの形状は、Strands ネイティブのパス (Path A) や古い連携がセッションをどう表現しているかをデバッグする場合、あるいはスパンを出力せずログイベントのみを出力するツールを扱う場合に、有用な背景知識として残ります。

**要点:** どのフレームワークであっても、評価が見る必要があるのは (1) ユーザーのプロンプト、(2) 最終的な回答、(3) ツール呼び出しとその引数および結果です。OpenInference のスパンはこの 3 つすべてを保持します。だからこそ Path B は偽装なしでどのフレームワークにも機能します。
