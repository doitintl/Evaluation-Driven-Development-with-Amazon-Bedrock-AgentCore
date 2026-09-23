---
title: "Path A.2 AgentCore Runtime へのエージェントのデプロイ"
weight: 20
---

**シナリオ。** モジュール 0 では、ノート PC で実行するのと同じように、エージェントを Code Editor の EC2 インスタンス上の通常のプロセスとして実行しました。そのプロセスの外側からは何が行われたのか見えませんでした。本番のエージェントをそのように動かすことはないため、このステップではマネージドインフラである **Amazon Bedrock AgentCore Runtime** に移します。これにより、自分で書く必要のないテレメトリも得られます。

:::alert{type="info" header="学習: Amazon Bedrock AgentCore Runtime とは"}
**AgentCore** は、AI エージェントを本番で実行・運用するためのマネージドサービス群です。このワークショップではそのうち 3 つを使います。**Runtime** (エージェントをホストする)、**Observability** (トレースとレコードを収集する)、**Online Evaluation** (セッションを採点する) です。Memory、Gateway、Identity といった他のコンポーネントもありますが、このワークショップでは扱いません。

**Runtime** は、独自の IAM 実行ロールを持つマネージドコンテナでエージェントのコードをホストし、その隣にテレメトリのサイドカーを注入します。このサイドカーがあるため、Path A では計測コードが不要です。サイドカーが代わりにトレースとレコードを出力します。

Path B はエージェントを現在の場所で動かし続け、代わりに手動で計測します。どちらも同じ評価パイプラインに到達します。どちらかがより「本番的」ということはありません。違いはコンテナを誰が運用するかです。

[AgentCore Runtime のドキュメント](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime.html)
:::

## 2.1: AgentCore プロジェクトを確認する

このパスでは **AgentCore CLI** (`@aws/agentcore`、Node パッケージ) を使います。プロジェクトには、何をデプロイするかを記述した `agentcore/` ディレクトリが含まれています。

Code Editor の **Explorer** で `travel-agent-strands/agentcore/agentcore.json` を開きます。重要なフィールドは次のとおりです。

```json
{
  "name": "travelAgentStrands",
  "managedBy": "CDK",
  "runtimes": [
    {
      "name": "travelAgent",
      "build": "CodeZip",
      "entrypoint": "runtime/main.py",
      "codeLocation": ".",
      "runtimeVersion": "PYTHON_3_12",
      "networkMode": "PUBLIC",
      "protocol": "HTTP",
      "environmentVariables": {
        "AWS_REGION": "us-east-1",
        "MODEL_ID": "us.anthropic.claude-sonnet-4-6",
        "UNIFIED_TRACES_DESTINATION_ENABLED": "false"
      }
    }
  ],
  "memories": []
}
```

次に `travel-agent-strands/runtime/main.py` を開きます。短いファイルです。このラッパーは Coordinator を `@app.entrypoint` として公開し、Runtime がリクエストごとに 1 回呼び出します。

その後、このページの残りのためにシェルを準備します。

```bash
source /workshop/edd-workshop/config.env
cd /workshop/edd-workshop/travel-agent-strands
```

:::alert{type="info" header="仕組み: これらのフィールドの意味"}
- **`build: CodeZip`**: Python コードが zip 化されてアップロードされます。Docker もローカルビルドも不要です。`uv` が依存関係を解決し、Code Editor にプリインストールされています。
- **`entrypoint: runtime/main.py`**: Coordinator を `BedrockAgentCoreApp` でラップします。`src/coordinator.py` から `create_coordinator_agent()` をインポートし、`payload["prompt"]` を取り出してエージェントを実行します。
- **`memories: []`**: このエージェントは呼び出しごとにステートレスなので、AgentCore Memory は作成されず、デプロイにメモリの権限は不要です (旧ツールキットの `--disable-memory` に相当する新 CLI の書き方)。
- **`UNIFIED_TRACES_DESTINATION_ENABLED: "false"`**: スパンの書き込み先を固定します。下のボックスを参照してください。
:::

:::alert{type="info" header="学習: スパンの 2 つの保存先と、このワークショップが一方を選ぶ理由"}
AgentCore は、エージェントのスパンを次の 2 か所のいずれかに書き込めます。

| 保存先 | スパンの格納場所 |
|---|---|
| 共有 (このワークショップで使用) | アカウント全体の `aws/spans` ロググループ |
| 統合 (新しいデフォルト) | エージェント自身のロググループ内の `spans` ストリーム |

統合ストレージは、エージェントのスパン、プロンプト、ログをまとめて保持するため、エージェント単位の IAM スコープ設定と暗号化が可能になります。2026 年 7 月に新規作成エージェントのデフォルトになり、エージェントが ADOT 0.18.0 以降を実行している場合にのみ有効になります。

このワークショップではこの変数を `false` に設定し、**マネージドなサイドカーがどの ADOT バージョンを搭載していても、すべての参加者が同じ保存先になる** ようにしています。以降のすべてのステップとモジュール 2 から 4 は `aws/spans` を読むため、これを固定することで、足元で変わり得るプラットフォームのデフォルトに依存せず、手順が正しいままになります。

ご自身のプロジェクトでは、未設定のままにして統合のデフォルトを使うことを推奨します。そのほうが設計として優れています。クエリを書く前に、どちらを使っているか把握しておいてください。
[スパンの保存先に関するドキュメント](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html)
:::

## 2.2: AgentCore CLI を確認する

CLI は Code Editor にプリインストールされています。

```bash
agentcore --help
```

`create`、`deploy`、`invoke`、`status`、`logs` を含むコマンド一覧が表示されるはずです。

:::alert{type="warning" header="command not found が出る場合"}
インストールします (Node 20+ はプリインストール済みです)。

```bash
npm install -g @aws/agentcore
```
:::

:::alert{type="info" header="学習: CDK とは何か、CLI がなぜそれを使うのか"}
**AWS CDK** (Cloud Development Kit) はインフラをプログラミング言語で記述し、そこから CloudFormation テンプレートを生成します。AgentCore CLI は内部で CDK を使っているため、`agentcore deploy` は実際には「CDK アプリを合成し、生成された CloudFormation スタックをデプロイする」という処理です。

このワークショップで CDK を理解している必要はありません。CLI が記述とデプロイを行います。これが起きていると知っておく理由は、何かが失敗したときにエラーが CLI ではなく CloudFormation から来る可能性があり、CloudFormation コンソールに実際のスタックが見つかるからです。

CDK にはブートストラップと呼ばれる、アカウントごとに 1 回だけ必要なセットアップがあります。Code Editor はプロビジョニング時にすでに実行済みです。
[AWS CDK のドキュメント](https://docs.aws.amazon.com/cdk/v2/guide/home.html)
:::

:::alert{type="warning" header="後のデプロイで環境がブートストラップされていないと表示される場合"}
`cdk bootstrap` を一度実行し、デプロイを再試行してください。
:::

## 2.3: プロジェクトをこのアカウントに向ける

`agentcore deploy` には、デプロイ先のアカウントとリージョンを指定する `aws-targets.json` が必要です。**この** ワークショップアカウント向けに生成します (このファイルはアカウント固有なのでコミットされていません)。

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
cat > agentcore/aws-targets.json <<EOF
[
  { "name": "default", "account": "$ACCOUNT_ID", "region": "us-east-1" }
]
EOF
cat agentcore/aws-targets.json
```

デプロイ前にプロジェクト設定を確認します。

```bash
agentcore validate
```

期待される出力は 1 語です。

```
Valid
```

:::alert{type="info" header="学習: `validate` が確認することと、無効な場合の表示"}
`validate` は `agentcore.json` に対するスキーマチェックです。ファイルが有効な JSON であり、すべてのフィールドが API が受け付ける値を持つことを確認します。成功すると `Valid` だけを表示します。

無効な場合は問題を明示します。enum 値が不正なら、受け付けられる値が列挙されます。

```
/workshop/edd-workshop/travel-agent-strands/agentcore/agentcore.json:
  - root: expected "PYTHON_3_10" | "PYTHON_3_11" | "PYTHON_3_12" | "PYTHON_3_13" | "PYTHON_3_14"
```

不正な JSON は位置付きで報告されます。

```
Invalid JSON in agentcore.json: Expected property name or '}' in JSON at position 2 (line 1 column 3)
```

**確認しないことも把握してください。** これは設定ファイルへのチェックであり、プロジェクトやアカウントへのチェックではありません。存在しないファイルを指す `entrypoint` でも `Valid` と報告されます。IAM 権限の不足、モデルアクセスの不足、ブートストラップされていない CDK 環境も同様です。`Valid` は「このファイルは正しい形式である」という意味で、「このデプロイは成功する」という意味ではありません。

`deploy` 自体がチェックを行うため、実行は任意です。ただし `deploy` には数分かかるため、ここで捕まえたタイプミスは CloudFormation のロールバック途中で発見するものではなくなり、2 秒をかける価値があります。
:::

## 2.4: `agentcore deploy`

```bash
agentcore deploy -y
```

これにより次のことが行われます。

- `runtime/main.py` と `src/` を **CodeZip** アーカイブとしてパッケージ化します (`uv` が `requirements.txt` を解決)。
- CDK アプリを合成し、CloudFormation スタックとしてデプロイします。IAM 実行ロールの作成、コードのアップロード、AgentCore Runtime のプロビジョニングを行います。
- Runtime が準備完了になるまでポーリングします。

CLI は各ステップを `✓` で示し、その後スタックの出力と次にすべきことを表示します。抜粋を示します (プレースホルダーの部分にはご自身のアカウント ID とランタイムのサフィックスが入ります)。

```
✓ Check bootstrap status
✓ Check stack status
✓ Deploy to AWS
✓ Persist deployment state

✓ Deployed to 'default' (stack: AgentCore-travelAgentStrands-default)

Outputs:
  ApplicationAgentTravelAgentRuntimeArnOutput93A546CA: arn:aws:bedrock-agentcore:us-east-1:<account>:runtime/travelAgentStrands_travelAgent-<id>
  ApplicationAgentTravelAgentRoleArnOutputD87AEDAF: arn:aws:iam::<account>:role/AgentCore-travelAgentStra-ApplicationAgentTravelAge-<id>
  ApplicationAgentTravelAgentRuntimeIdOutput727EEFDB: travelAgentStrands_travelAgent-<id>
  StackNameOutput: AgentCore-travelAgentStrands-default
Next: agentcore invoke | agentcore status

Log: agentcore/.cli/logs/deploy/deploy-<timestamp>.log
```

合計 2 〜 5 分です。ビルドの様子を見たい場合は `-v` を付けるとリソース単位のデプロイイベントが表示されます。

この `RuntimeIdOutput` の値が、Path A.2 の取得ステップがこれから読み取るランタイムのサフィックスなので、今ここで目を通しておく価値があります。

各実行は `Log:` のパスに完全な記録も書き出します。各ステップに所要時間が付き、実行の最後には `Total Duration` が表示されます (新しいサンドボックスアカウントでは 1 分 50 秒)。このログはターミナルより詳細で、デプロイが遅い場合や失敗した場合に最初に見る場所です。

:::alert{type="info" header="初回デプロイで問題のように見えるが問題ではない 2 つの表示"}
**1. 依存関係バージョンの通知。** `Sync CDK dependencies` のステップで次のように報告されることがあります。

```
Your project was created before the AgentCore CLI managed dependency versions.
We've updated agentcore/cdk/package.json so the CLI keeps these dependencies
on versions it has been tested with (patch updates still apply automatically):

  @aws/agentcore-cdk   ^0.1.0-alpha.19  → 0.1.0-alpha.45
  aws-cdk-lib          ^2.248.0         → ~2.261.0
  ...
```

CLI が、チェックイン済みの CDK アプリをテスト済みのバージョンに固定しています。対応は不要です。

**2. Application Signals の権限警告。** 最後、`COMPLETED SUCCESSFULLY` の直前に表示されます。

```
[WARN] Transaction search setup warning: Insufficient permissions to enable
Application Signals: User: arn:aws:sts::<account>:assumed-role/...-EditorRole/...
is not authorized to perform: application-signals:StartDiscovery
```

CLI が代わりに Transaction Search を有効にしようとしますが、Code Editor のロールは意図的にその権限を付与していません。**Path A.3 で Transaction Search を正しく有効にします**。CloudFormation と X-Ray API 経由で行うため、この警告は無視して問題ありません。デプロイ自体は成功しています。警告の下の `COMPLETED SUCCESSFULLY` の行を読んでください。
:::

:::alert{type="warning" header="Bedrock または Marketplace の AccessDeniedException が出る場合"}
アカウントの `us.anthropic.claude-sonnet-4-6` のモデルサブスクリプションがまだ伝播中です。Code Editor はプロビジョニング時に事前ウォームアップするため、これはまれです。60 〜 90 秒待って再実行してください。モジュール 0 のトラブルシューティングの注記も参照してください。
:::

## デプロイしたエージェントのスモークテスト

エージェントは Code Editor 内ではなく、マネージドインフラ上で動作するようになりました。CLI はプロンプトを直接受け取り、JSON のエンベロープは不要です。

```bash
agentcore invoke "What is the Grand Museum?"
```

期待される結果: モジュール 0 と同じ Luminara に基づく回答で、営業時間、休館日、料金を含みます。同じエージェント、同じデータ、違う置き場所です。

:::alert{type="warning" header="invoke がタイムアウトする場合"}
Runtime のコールドスタートに時間がかかりすぎました。同じコマンドを再実行してください。
:::

## 自動生成された名前を取得する

名前は Runtime が生成したため、次のステップではアカウントから読み戻す必要があります。1 つのコマンドで両方を取得して保存します。

```bash
cd /workshop/edd-workshop
./scripts/capture-runtime-names.sh
source config.env
```

期待される出力: 2 つの値と、`config.env` に書き込まれた旨の確認。

```
  RUNTIME_LOG_SUFFIX   = travelAgentStrands_travelAgent-ABC123-DEFAULT
  RUNTIME_SERVICE_NAME = travelAgentStrands_travelAgent.DEFAULT
```

これらは `config.env` に書き込まれ、新しいターミナルはログイン時に必ずこれを読み込むため、Path A の残りとモジュール 2 は自動的に値を取得します。再実行する必要はありません。

:::alert{type="info" header="学習: Runtime が 2 つの異なる名前を生成する理由"}
Runtime は同じアイデンティティの 2 つの形式を使い、これらは交換可能ではありません。

| 値 | 形 | 使用箇所 |
|---|---|---|
| `RUNTIME_LOG_SUFFIX` | ランタイム ID を保持、ハイフン連結 | CloudWatch のロググループ名。つまり Path A.3 の CFN パラメーター |
| `RUNTIME_SERVICE_NAME` | ランタイム ID を除外、**ドット** 連結 | すべてのレコードに刻印される `service.name`。つまりモジュール 2 の評価器のフィルター |

モジュール 2 に誤ったほうを渡すと、フィルターが何にも一致しません。どのセッションも採点されず、それを知らせるエラーもなく、結果のロググループが空になるだけです。

スクリプトはこれを避けるため、`RUNTIME_SERVICE_NAME` をロググループ名から導出するのではなく、実際のログレコードから読み取ります。そのため Runtime が実際に書き込む値からずれることはありません。仕組みを見たい場合は `scripts/capture-runtime-names.sh` を開いてください。
:::

:::alert{type="warning" header="スクリプトがロググループが見つからないと表示する場合"}
Runtime は **最初の呼び出し** 時にロググループを作成します。つまり、上のスモークテストがまだ実行されていないということです。実行してからスクリプトを再実行してください。
:::

:::alert{type="warning" header="スクリプトが複数のロググループを見つけたと表示する場合"}
このアカウントに複数のランタイムがデプロイされており、スクリプトは推測を行いません。見つかった名前を表示するので、今デプロイしたものを指定して再実行してください。

```bash
./scripts/capture-runtime-names.sh travelAgentStrands_travelAgent-ABC123-DEFAULT
```
:::

## デプロイしたもの

- AgentCore CLI (内部では CDK) でデプロイされた、AgentCore Runtime 上で動作する CodeZip パッケージの Strands エージェント。
- 自動注入された OTEL サイドカー。トレースと正規の `invoke_agent` ログイベントを出力し、`service.name = <agentName>.<endpoint>` (ドット連結、ランタイム ID なし) を付与します。

次は Path A.3 です。そのサービス名で可観測性の CFN をデプロイします。
