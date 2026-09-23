---
title: "Path A.5 振り返りと次の内容"
weight: 50
---

## 構築したもの

すべての呼び出しに対する完全なトラジェクトリのウォーターフォール。しかも自分では **OTEL のコードも環境変数もゼロ** です。

![1 回の呼び出しのトレース詳細。ボックス 1: スパンのツリー、つまりエージェントのトラジェクトリ。ボックス 2: リソース属性内の service.name、モジュール 2 がフィルターに使う結合キー](/static/images/module-1/1a-trace-waterfall.png)

まだ空のままなのはエージェントの **Evaluations** タブだけで、*「No evaluation configurations to display in the selected time range」* と表示されます。まだ評価器が接続されていないからです。モジュール 2 でこれを解決します。

| ステップ | 実施内容 | 手間 |
|---|---|---|
| A.2 | `agentcore deploy` の後、CloudWatch から 2 つのサービス名を読み取る | コマンド 5 つ。うち 1 つは 2 分のデプロイ |
| A.3 | ロググループのサフィックスで `agentcore-observability.yaml` をデプロイ | CFN デプロイ 1 回、チェック 2 つ |
| A.4 | 呼び出しと確認 | 呼び出し 3 回、確認スクリプト 2 回 |

:::alert{type="success" header="持ち帰るべき 1 つの考え: 可観測性の深さが評価の質の上限を決める"}
今接続したデータは、モジュール 2 のジャッジが読むものと *まったく同じ* です。何を捕捉するかが、何を採点できるかを決めます。

| 捕捉する内容 | ジャッジが評価できること |
|---|---|
| 入力と出力のみ | 最終的な回答が正しそうに見えるか |
| **+ ツール呼び出し (現在の状態)** | **エージェントが正しいツールを正しい順序で使ったか** |
| + 推論のスパン | 計画の質、およびハルシネーションを起こしたか |

ツール呼び出しのトラジェクトリを捕捉したため、モジュール 2 はエージェントが *何を* 言ったかだけでなく *どうやって* そこに至ったかも採点できます。`plan_route` より前に `query_sites` を呼んだのか、それとも営業時間を作り出したのか、です。
:::

:::alert{type="info" header="任意: シンプルさと引き換えにしたもの"}
マネージドなサイドカーは摩擦の最も少ない道ですが、次の点を受け入れることになります。

- **デプロイ先が AgentCore Runtime であること。** このエージェントを自前の VM、コンテナ、Kubernetes で動かすことはできません。それが必要なら Path B が答えです。
- **自動生成されたサービス名。** そのため手順が少し不自然になります。名前を知るために先にエージェントをデプロイし (A.2)、その後に可観測性をデプロイします (A.3)。取得を省くため `agentcore.json` に `service.name` をハードコードするチームもあり、それでも問題ありません。
- **CLI のパッケージングモデル。** このデプロイは **CodeZip** を使いました。`agentcore deploy` が `runtime/main.py` と `src/` を zip 化し、`uv` で `requirements.txt` を解決し、アーカイブをアップロードします。Dockerfile もイメージビルドも、経路上のどこにも ECR リポジトリもありません。そのほうがシンプルですが、ランタイム環境は自分で固定したものではなく、CLI のマネージドなベースが提供するものになります。

知っておく価値があること: `agentcore deploy` は CDK、CloudFormation、IAM の薄いラッパーです。それが作るものを手作業で構築することもできますが、やりたくはないでしょう。
:::

## 次はどこへ

- **[モジュール 2](../../../02-continuous-monitoring/)**: すべてのセッションを採点する自動ジャッジを接続し、空だったタブがスコアで埋まる様子を見ます。
- **モジュール 3**: モデル差し替えとプロンプト変更の実験によるトラジェクトリを考慮した評価。
- **モジュール 4**: コーディングエージェントで本番トラフィックを開発時のテストケースに変換します。

:::alert{type="info" header="任意: 終了時に Path A を削除する"}
Workshop Studio はイベント終了時にアカウント全体を削除するため、これが必要なのはご自身のアカウントで実行している場合だけです。

```bash
# Tear down the Runtime + IAM + CDK stack the AgentCore CLI created.
# `remove all` clears the resources from the project config, then `deploy`
# applies the removal (tears down the CloudFormation stack).
cd /workshop/edd-workshop/travel-agent-strands
agentcore remove all
agentcore deploy -y

# Tear down the observability CFN
aws cloudformation delete-stack --stack-name edd-observability
```
:::
