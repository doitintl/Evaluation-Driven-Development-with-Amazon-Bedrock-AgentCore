---
title: "0. セットアップとトラベルエージェントの実行"
weight: 10
---

このモジュールでは、スタックが動作していること、そしてトレースが CloudWatch に流れ込むことを確認します。

**このモジュールのチェックリスト:**

1. Workshop Studio 経由で AWS コンソールにサインインする。
2. Code Editor の URL を取得する。
3. エージェントを実行し、回答することを確認する。
4. AWS 認証情報と CLI のバージョンを確認する。
5. 制約の多いプロンプトを実行し、トラジェクトリを読み取る。
6. `config.env` を確認し、空の GenAI Observability ダッシュボードを見る。

:::alert{type="info" header="背景: 対象読者、前提条件、費用 (任意の読み物)"}
**目標、学習成果、対象読者、前提条件** の全体像は、[ワークショップ概要](../) を参照してください。要約すると次のとおりです。

- **対象:** 雰囲気ではなく測定可能な品質を求めて LLM エージェントを構築・運用する開発者と DevOps エンジニア。
- **学べること:** エージェントの可観測性の接続 (モジュール 1)、自動ジャッジによる全セッションの採点 (モジュール 2)、デプロイ前のトラジェクトリリグレッションの検出 (モジュール 3)、本番パターンのテストスイートへの取り込み (モジュール 4)。
- **前提条件:** AWS とコマンドラインの基本的な知識、および TypeScript / Python を読める程度の理解。AgentCore の経験は不要です。

**費用。** AWS 主催イベントでは、すべてが無償で提供される Workshop Studio のサンドボックスアカウント内で実行され、イベント終了時に自動的に削除されます。ご自身のアカウントの場合、このワークショップは課金対象のリソース (EC2 の Code Editor、Lambda、CloudWatch のログ、AgentCore の評価器、Bedrock の呼び出し) をデプロイし、全体で数米ドルの費用がかかります。終了時にはルートの CloudFormation スタックを削除してください ([クリーンアップセクション](../summary/) を参照)。
:::

## ステップ 1: AWS コンソールにサインインする

このワークショップでは複数のステップで AWS コンソールを開きます。これらのリンクは **ワークショップの参加者ロールとして** サインインしている場合のみ機能するため、最初に実施してください。

1. すでにサインインしている AWS アカウント (ご自身のもの、または勤務先のもの) からログアウトします。そうしないと、コンソールリンクが誤ったアカウントに接続されます。
2. Workshop Studio の **左ナビゲーション** で **AWS account access** を展開します。
3. **Open AWS console (us-east-1)** をクリックします。サインイン済みの新しいタブが開きます。

その新しいタブの右上に **`WSParticipantRole/Participant`** が表示され、リージョンが **バージニア北部 (us-east-1)** になっていることを確認してください。このタブはワークショップの残りの間、開いたままにします。

:::alert{type="warning" header="このステップを飛ばすと、以降のすべてのコンソールリンクが機能しません"}
このワークショップのコンソールリンク (GenAI Observability ダッシュボードなど) は、このセッションの存在を前提としています。リンクがサインインページに飛ぶ場合や誤ったアカウントが表示される場合は、ここに戻って Workshop Studio 経由でコンソールを再度開いてください。
:::

## ステップ 2: Code Editor の URL を取得する

Workshop Studio の左ナビゲーションから **Event dashboard** を開きます。スタックの出力が直接表示されるため、CloudFormation を開かずにコピーできます。

| 出力 | 内容 |
|---|---|
| `CodeEditorUrl` | ブラウザ上の VS Code |
| `ServiceName` | Path B が使用するデフォルトの OTEL `service.name` (`travel-agent-edd-workshop`) |

以降の操作はすべて Code Editor のターミナルで行います。

:::alert{type="info" header="評価インフラが事前デプロイされていない理由"}
多くの AWS ワークショップとは異なり、このワークショップでは AgentCore の評価および可観測性インフラを事前デプロイしていません。可観測性スタックはモジュール 1 で、評価器スタックはモジュール 2 で **あなた自身が** デプロイします。これは意図的です。本番環境で評価パイプラインをベンダーに事前デプロイさせることはないはずなので、自分で構築することに意味があります。事前デプロイされているのは VPC と Code Editor だけです。
:::

## ステップ 3: Code Editor を開いてエージェントを実行する

`CodeEditorUrl` をクリックします。ブラウザ版の VS Code が開き、ワークショップのリポジトリが `/workshop/edd-workshop` にクローンされています。

初回起動時に **「このフォルダー内のファイルの作成者を信頼しますか」** と尋ねられることがあります。**「はい、作成者を信頼します」** をクリックしてください。制限モードでは、ターミナルとこのワークショップが依存する拡張機能が無効のままになります。

ターミナルを開き (`Terminal → New Terminal`)、後でデプロイする CloudFormation テンプレートが配置済みであることを確認します。

:::code{language=bash showCopyAction=true showLineNumbers=false}
ls /workshop/edd-workshop/cfn/
:::

`agentcore-observability.yaml` (モジュール 1) と `agentcore-eval-and-obs.yaml` (モジュール 2) が見えるはずです。これらはプロビジョニング時に配置されているため、後の `aws cloudformation deploy --template-file cfn/...` コマンドはダウンロード手順なしで動作します。

次に、事前設定されたデフォルト値を読み込んでエージェントを実行します。

:::code{language=bash showCopyAction=true showLineNumbers=false}
source /workshop/edd-workshop/config.env
cd /workshop/edd-workshop/travel-agent
npx tsx src/main.ts "What's at the Grand Museum?"
:::

**これがどこで動いているかは、後で重要になります。** このコマンドは、ノート PC で実行した場合とまったく同じように、Code Editor の EC2 インスタンス上の通常のプロセスとしてエージェントを起動しました。動作はしますが、**そのプロセスの外側からは何が行われたのかまったく見えません**。トレースもレコードもなく、採点する対象もありません。モジュール 1 はこれを解決します。

期待される出力 (抜粋。エージェントは非決定的なので文言は変わります):

```
Here's what I found about the **Grand Museum of Luminara**:

- **Category:** History
- A sprawling museum housing centuries of Luminaran history, from
  ancient artifacts to modern art installations.
- **Hours:** 09:00 – 18:00
- **Closed:** Mondays
- **Suggested visit:** ~2 hours
- **Ticket Price:** $25

It sounds like a great stop for history and art lovers! Would you like
to include it in a trip itinerary?
```

:::alert{type="info" header="この出力からわかること (任意の読み物)"}
Coordinator が `query_sites` ツールを呼び出し、ツールがインラインのモックデータから Grand Museum のレコードを返し、Coordinator が親しみやすい回答を合成しました。これで Node、Bedrock クライアント、エージェントのコードがすべて動作していることが確認できます。正確な文言は重要ではありません。不変条件は、正しい営業時間、正しい休館日、正しい料金です。後の評価がこれらの値に対して採点するからです。

`Cannot find module 'tsx'` が出た場合は、一度 `npm install` を実行してください。依存関係はプロビジョニング時にインストールされているため、これはまれです。
:::

## ステップ 4: AWS 認証情報と CLI のバージョンを確認する

両方のチェックを実行します。

:::code{language=bash showCopyAction=true showLineNumbers=false}
aws sts get-caller-identity --region us-east-1
aws --version
:::

期待される結果: `:assumed-role/main-stack-CodeEditor-...-EditorRole-.../i-<instance-id>` で終わる ARN、および最近の AWS CLI v2。

`AWS_PROFILE` や `AWS_ACCESS_KEY_ID` を **エクスポートしないでください**。Workshop Studio はデフォルトのチェーンを通じて認証情報を提供しており、これを上書きすると以降のすべてのステップが壊れます。

:::alert{type="warning" header="Unable to locate credentials が出たら、ここで止めてください"}
先に進まないでください。以降のすべてのステップでこの認証情報が必要です。ファシリテーターに相談してください。このモジュールのトラブルシューティングにある、残留した `AWS_` 環境変数の項目も参照してください。
:::

:::alert{type="info" header="2 つのロール、2 つの役割 (任意の読み物)"}
Code Editor の EC2 は、ターミナルで実行するすべての操作 (Bedrock の呼び出し、AgentCore の評価管理、ログの読み書き、CFN のデプロイ) にスコープ設定された `EditorRole` インスタンスプロファイルを使用します。`WSParticipantRole` はステップ 1 のコンソール専用の別ロールで、`ReadOnlyAccess` に加えてワークショップ自身のリソース向けの小さな書き込み許可リストを持ちます。
:::

:::alert{type="info" header="後のステップが `argument operation: Invalid choice` で失敗する場合"}
AWS CLI が古く、AgentCore の `bedrock-agentcore-control` サブコマンドに対応していません。Code Editor はプロビジョニング時に最新の CLI をインストールするため、これはまれです。その場でアップグレードします。

```bash
curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
(cd /tmp && unzip -q awscliv2.zip && sudo ./aws/install --update)
hash -r && aws --version
```

代わりに macOS のローカルで実行していますか。Linux 用インストーラーはダウンロードできても `cannot execute binary file` で失敗するため、macOS パッケージを使ってください。

```bash
curl -fsSL "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o /tmp/AWSCLIV2.pkg
sudo installer -pkg /tmp/AWSCLIV2.pkg -target /
hash -r && aws --version
```
:::

## ステップ 5: エージェントを実行してトラジェクトリを読む

制約の多いプロンプトを Coordinator に送ります。

:::code{language=bash showCopyAction=true showLineNumbers=false}
npx tsx src/main.ts "Plan a 2-day Luminara trip focused on history, arriving Monday."
:::

約 30 秒後、Coordinator が 2 日間の旅程を返します。

**確認すべき点は 1 つです。** **Grand Museum** が Day 1 (月曜) ではなく **Day 2 (火曜)** に配置されること。月曜は休館だからです。サマリーには通常その理由が明記されます。たとえば「Grand Museum moved to Tuesday (closed Monday)」のように。

その回答の裏で、Coordinator は 3 つのツールを順に呼び出しました。歴史系の観光地を調べる `query_sites`、休館日を考慮したスケジュールを作る `plan_route`、そして食事場所のための `suggest_dining` です。**この順序はここでは見えません。** `src/main.ts` は最終的な回答のみを表示するため、トラジェクトリは結果から推測しているにすぎません。これを可視化することがまさにモジュール 1 の役割であり、可観測性が評価より先に来る理由です。

:::alert{type="info" header="この順序が重要な理由 (任意の読み物)"}
Coordinator は `plan_route` より前に `query_sites` を呼び出す必要があります。そうすればルートプランナーが正確な休館日データを持てます。Grand Museum が Day 1 (月曜) に予定されていたら、トラジェクトリが壊れています。モジュール 2 ではまさにそれを評価スコアで検出する方法を示し、モジュール 3 では再現可能なテストにします。
:::

## ステップ 6: `config.env` を確認し、空のダッシュボードを見る

モジュール 1 とモジュール 2 のデプロイは `ARTIFACTS_BUCKET` と `ARTIFACTS_PREFIX` に依存するため、5 つの値がすべて設定されていることを確認します。

:::code{language=bash showCopyAction=true showLineNumbers=false}
source /workshop/edd-workshop/config.env
echo "AWS_REGION=$AWS_REGION"
echo "SERVICE_NAME=$SERVICE_NAME"
echo "ARTIFACTS_BUCKET=$ARTIFACTS_BUCKET"
echo "ARTIFACTS_PREFIX=$ARTIFACTS_PREFIX"
echo "MODEL_ID=$MODEL_ID"
:::

`ARTIFACTS_BUCKET` はイベントごとの Workshop Studio バケットで、`ws-event-<event-id>-us-east-1` のような名前です。`ARTIFACTS_PREFIX` は `/assets/` で終わるビルド固有のパスです。正確な値はイベントごとに異なるため、他の人の値と比較しないでください。モジュール 1 とモジュール 2 は両方を渡し、`eval_provisioner` Lambda が S3 から読み込めるようにします。

次に、ステップ 1 の AWS コンソールタブに切り替え、モジュール 1 で埋めていくダッシュボードを開きます。

1. **CloudWatch** を開きます。
2. 左ナビゲーションで **GenAI Observability** を展開します。
3. **Bedrock AgentCore** をクリックします。

直接リンク: [GenAI Observability, Bedrock AgentCore](https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#gen-ai-observability/agent-core) (ステップ 1 のサインイン済みコンソールタブでのみ機能します)。

**期待される結果: 空のダッシュボード。これで正しいです。** 正しい場所にいて「変更前」の状態であることを、次の 2 つが示します。

1. **「AgentCore Observability requires span ingestion」** という注意書きと **Configure** ボタン。Transaction Search がまだ有効になっていないことを伝えています。
2. メトリクスとエージェント一覧が表示される場所にある **「No data / Enable Transaction Search」**。

![どのエージェントも計測されていない状態の GenAI Observability ダッシュボード。ボックス 1: Transaction Search がまだ有効でないことを示す「AgentCore Observability requires span ingestion」の注意書き。ボックス 2: OTEL メトリクスの代わりに表示される「No data, Enable Transaction Search」](/static/images/module-1/00-genai-obs-before.png)

モジュール 1 で Transaction Search を有効にし、ここに戻ってダッシュボードが埋まる様子を確認します。

:::alert{type="info" header="仕組み: Configure はクリックしないでください"}
このボタンはコンソールから Transaction Search を有効にします。触らないでください。モジュール 1 では代わりに CloudFormation テンプレートで有効にします。そうすることでご自身のアカウントに持ち帰れる成果物が手に入り、またワークショップの後のステップがデプロイした内容と一致します。
:::

:::alert{type="info" header="Application Signals の下を探していますか。場所が違います"}
**GenAI Observability** は CloudWatch の左ナビゲーションにある独立したトップレベル項目です。**Application Signals (APM)** はそのすぐ下にある別の項目で、エージェントのダッシュボードは含まれていません。
:::

## ここで何が起きたか

可観測性の計測なしで Coordinator を実行しました。回答は返ってきますが、何もトレースされていません。モジュール 1 でこれを接続します。パスは 1 つの問いで選びます。*あなたのエージェントは Strands Agents SDK を使っていますか。*

- **[Path A、AgentCore Runtime 上の Strands](../01-agentic-observability/path-a-strands/)**: Strands SDK のエージェント向け。AgentCore Runtime にデプロイすると、マネージドなサイドカーがテレメトリを出力します。約 20 分。
- **[Path B、その他すべてのフレームワーク](../01-agentic-observability/path-b-any-framework/)**: それ以外すべて (LangGraph、CrewAI、独自実装、またはこのワークショップの **pi-mono**)。ライフサイクルイベントを OpenTelemetry のスパンにマッピングする小さな OpenInference アダプターを追加します。約 45 分。

どちらも同じ評価可能なテレメトリに収束するため、モジュール 2 から 4 はどちらのパスでも同じように動作します。

## トラブルシューティング

:::alert{type="warning" header="`aws sts get-caller-identity` が失敗する、または誤ったロールを返す"}
ターミナルで `AWS_PROFILE`、`AWS_ACCESS_KEY_ID`、`AWS_SESSION_TOKEN` の環境変数が設定されていないか確認します: `env | grep AWS_`。設定されている場合は `unset AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN` を実行して再試行してください。Workshop Studio の Code Editor は EC2 インスタンスメタデータサービスに依存しています。
:::

:::alert{type="warning" header="`npx tsx src/main.ts` が aws-marketplace:Subscribe の AccessDeniedException で失敗する"}
新しい AWS サンドボックスアカウントでは、AWS Marketplace で Bedrock の Sonnet 4.6 モデルにまだサブスクライブしていません。EC2 の IAM ロールからの最初の呼び出しが自動サブスクライブの経路を起動し、伝播に約 60-90 秒かかります。Workshop Studio のアカウントでは、最初の呼び出しでこれに当たることがよくあります。

90 秒待ってから同じコマンドを再実行してください。2 回目で通常は成功します。3 回試しても失敗する場合は、ファシリテーターに Bedrock コンソールで `us.anthropic.claude-sonnet-4-6` のモデルアクセスを確認してもらってください。
:::

:::alert{type="warning" header="`npm install` が権限エラーで失敗する"}
Code Editor のホームディレクトリは `ec2-user` アカウントが所有しています。`root` としてターミナルを開いた場合 (Workshop Studio ではまれです)、`su - ec2-user` で戻ってください。`npm install` がネットワークエラーを報告する場合は、一度再試行してください。新しいスタックでは NAT ゲートウェイの外向き通信が安定するまで少し時間がかかることがあります。
:::

:::alert{type="warning" header="GenAI Observability にトレースがない"}
現時点ではそれが期待される状態です。エージェントは応答を返しますが、モジュール 1 で接続するまでテレメトリは出力されません (Path A は AgentCore Runtime にデプロイし、Path B は OpenInference アダプターを追加します)。それまではターミナルの出力でトラジェクトリを確認してください。
:::

すべて問題なければ、**[モジュール 1: エージェントの可観測性](../01-agentic-observability/)** に進み、ご自身の構成に合うパスを選んでください。
