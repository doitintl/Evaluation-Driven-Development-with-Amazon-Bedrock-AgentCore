---
title: "サマリーと次のステップ"
weight: 90
---

これで EDD ループの全体を端から端まで構築しました。生のトレースから、自動採点、トラジェクトリを考慮した評価、そして本番由来のグラウンドトゥルースまでです。

## 4 つの問いへの答え

| モジュール | 問い | 答え |
|---|---|---|
| 1. エージェント可観測性 | 何が起きたか | CloudWatch の OTEL トレース + 構造化ログレコード |
| 2. 継続的モニタリング | エージェントは良かったか | Builtin.Helpfulness がすべてのセッションを自動採点 |
| 3. トラジェクトリ評価 | 具体的に何が壊れたか | フレームワーク評価が、コンテンツジャッジの見落とす経路のリグレッションを捉える |
| 4. グラウンドトゥルースのループ | 「良い」とはどうあるべきか | 本番データが継続的にテストスイートに情報を与える |

## 残る洞察

1. **可観測性と評価は別の関心事である。** トレースは *何が起きたか* を教え、評価は *それが良かったか* を教えます。それぞれが自分のペースで進化できるよう、独立してデプロイしてください。

2. **1 つではなく 2 つのレンズ。** AgentCore Online Evaluation (LLM-as-Judge、本番トラフィック) は予期しなかったコンテンツのリグレッションを捉えます。TS のフレームワーク評価スキャフォールドはトラジェクトリのリグレッションを捉えます。互いのテストで落ちるので、両方が必要です。

3. **トラジェクトリとコンテンツは独立した次元である。** モデルの差し替えはコンテンツ品質を改善しつつ、トラジェクトリの遵守を静かに劣化させることがあります。トラジェクトリのレンズがなければ、そのリグレッションを出荷していたでしょう。

4. **グラウンドトゥルースはドリフトする。** ローンチ時に書かれたテストケースは、現実ではなく開発者の想定を表します。本番のパターンは、お客様が実際に何を尋ねるかを明かします。ループを閉じること (本番 → テストケース → 改善 → 本番) が、評価の誠実さを保ちます。

5. **配線は成文化することでスケールする。** 2 つの Power (skill)、1 つは配線用、1 つは EDD 開発ループ用が、シニアエンジニアの習慣を、チームが新しいエージェントを出荷する方法そのものに変えます。

## チームに持ち帰るもの

- **可観測性の CFN** (`cfn/agentcore-observability.yaml`) と **評価の CFN** (`cfn/agentcore-eval-and-obs.yaml`) は再利用可能なテンプレートです。どのエージェントプロジェクトにも投入できます。
- `travel-agent/eval/` の **評価スキャフォールド** (`cases.ts`、`judge.ts`、`trajectory.ts`、`run-experiment.ts`) はテンプレートです。`cases.ts` をご自身のドメインに置き換えてください。
- `kiro-powers/` の **2 つの Power** が配線とケースファーストの開発を自動化します。どのコーディングエージェントでも適用できます。
- **本番から開発への抽出パターン** (モジュール 4) は、Online Eval の採点があるどのエージェントでも機能します。低スコアのセッションは、もっとも価値の高いテストケース候補です。

## クリーンアップ

:::alert{type="success" header="AWS が運営するイベントでは、ここで読むのをやめてかまいません"}
イベント終了時に Workshop Studio がアカウント全体を回収するので、構築したものは残らず、課金も続きません。このセクションの残りは、**ご自身のアカウントでこのワークショップを実施している方** 向けです。そこでは重要になります。ルートスタックだけでは、デプロイしたもののほとんどが消えないからです。
:::

**ルートスタックでは不十分です。** 可観測性と評価のスタックは、ルートスタックの内側にネストではなく兄弟としてご自身でデプロイしており、ページ 3.4 はスタックなしで Lambda、IAM ロール、評価器を手で作りました。ルートスタックだけを削除すると、そのすべてが動き続けます。新しいトラフィックに対して **ジャッジモデルを呼び続ける ACTIVE な Online Evaluation Config** も含みます。

上から下へ、この順で進めてください。ここにあるものはすべて、AWS コンソールか、アカウント全体を見られる認証情報のご自身のターミナルで行えます。

**1. 評価スタック** (`edd-eval-and-obs`、モジュール 2)。これを **最初に** 削除してください。Online Evaluation Config を所有しており、その設定が評価器を保持している間は次のステップが成功しません。

**2. 3.4 のトラジェクトリ評価器** (そのページを実施した場合)。どのスタックにも属していません。

```bash
# The config from step 1 must already be gone, or this returns
# "Cannot delete a locked evaluator" (an evaluator attached to a live config).
aws bedrock-agentcore-control delete-evaluator \
  --evaluator-id "$(cat /tmp/traj_evaluator_id.txt)" --region us-east-1

aws lambda delete-function --function-name edd-trajectory-evaluator --region us-east-1
aws iam detach-role-policy --role-name trajectory-evaluator-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam delete-role --role-name trajectory-evaluator-role
```

**2.6 のカスタム評価器も削除してください** (そのページを実施した場合)。スタックを削除してもそれは一緒に消えません。実アカウントでの実測では、上のすべてのステップのあとでも `edd_workshop_travel_quality-...` が残っており、このページ末尾のクリーン確認がそれを捉えました。名前で見つけて削除してください。

```bash
aws bedrock-agentcore-control list-evaluators --region us-east-1 \
  --query 'evaluators[?contains(evaluatorId, `edd_workshop_travel_quality`)].evaluatorId' --output text

aws bedrock-agentcore-control delete-evaluator \
  --evaluator-id edd_workshop_travel_quality-XXXXXXXXXX --region us-east-1
```

**3. 可観測性スタック** (`edd-observability`、モジュール 1)。

**4. Path A のみ: AgentCore Runtime。** `agentcore deploy` は独自の CloudFormation スタック (`AgentCore-<project>-default`、たとえば `AgentCore-travelAgentStrands-default`) を作り、その中の Runtime は、ここでアイドル中も費用がかかる唯一のリソースです。

:::alert{type="warning" header="AWS が運営するイベントでは、コンソールではなく Code Editor のターミナルから削除してください"}
2 つのロールには相補的な穴があり、予想の逆です。実イベントアカウントでの実測です。

| | `DescribeStacks` (一覧) | `DeleteStack` |
|---|---|---|
| Code Editor のターミナル (`EditorRole`) | **拒否** | **動作** |
| コンソール (`WSParticipantRole`) | 動作 | **拒否** |

つまりコンソールはスタックを見せてくれた上で「no identity-based policy allows the `cloudformation:DeleteStack` action」と拒否し、ターミナルは一覧できないのに削除は問題なく行います。ターミナルから:

```bash
aws cloudformation delete-stack --stack-name AgentCore-travelAgentStrands-default --region us-east-1
```

成功時は何も出力しません。結果はコンソールの **Deleted** フィルターで確認でき、そこで `DELETE_COMPLETE` に達しました。ご自身のアカウントでアカウント全体の管理者認証情報があれば、どちらの経路でも動作し、コンソールのダイアログは確認のためスタック名の入力も求めます。
:::

**`agentcore destroy` は存在しません。** `agentcore destroy` は `error: unknown command 'destroy' (Did you mean deploy?)` と返します。現在のコマンド一覧は `agentcore --help` を実行してください。長く (約 30 コマンド。`deploy`、`invoke`、`logs`、`status`、`remove`、`telemetry`、`traces` など)、CLI のリリース間で変わるので、ここに挙げたどの一覧もスナップショットとして扱ってください。

**そして `agentcore remove` は AWS のテアダウンではありません**。これが重要な部分です。約 20 のサブコマンドを持ち、`evaluator`、`online-eval`、`runtime-endpoint`、`gateway` といった魅力的な名前が含まれます。それらはすべて、デプロイ済みのリソースではなく **プロジェクトの設定** を編集します。`agentcore remove online-eval --help` は自身を「Remove an online eval config **from the project**」と説明します。ですからここで何かを remove しても、アカウント内の Online Evaluation Config は削除されず、Runtime の CloudFormation スタックも削除されません。

したがってスタックを削除し、CLI はそのあとプロジェクトを片付ける手段として扱ってください。

```bash
cd /workshop/edd-workshop/travel-agent-strands
agentcore status            # confirm what is deployed before you delete it
```

**5. ルートスタック。** これで Code Editor の EC2 インスタンス、そのセキュリティグループ、ブートストラップが作ったロールが消えます。およそ 5 分です。

:::alert{type="info" header="Code Editor のターミナルからはスタックを一覧できません"}
Code Editor の `EditorRole` はワークショップ自身のリソースにスコープされているため、アカウント全体の `aws cloudformation describe-stacks` は `AccessDenied: not authorized to perform: cloudformation:DescribeStacks` を返します。これは想定どおりで、環境の不具合ではありません。スタックの削除には CloudFormation コンソールか、アカウント全体の読み取り権を持つ認証情報を使ってください。
:::

**上のどれも削除しないもの:**

- **Path A のみ: `CDKToolkit` スタック。** `agentcore deploy` は CDK のラッパーなので、初回実行がアカウントに CDK をブートストラップし、そのブートストラップは誰も教えてくれない別のスタックです。実アカウントで調べたところ、S3 のステージングバケットとそのバケットポリシー、ECR リポジトリ (`cdk-hnb659fds-container-assets-<account>-<region>`)、5 つの IAM ロール (`cfn-exec`、`deploy`、`file-publishing`、`image-publishing`、`lookup`)、そして SSM パラメーターを保持しています。安静時に大きな費用はかかりませんが、上のすべてのステップを生き延び、そのアカウントで CDK を使う他のものと共有されるので、このワークショップが唯一の CDK 利用者だった場合にのみ削除してください。
- アカウントレベルの `aws/spans` ロググループと X-Ray Transaction Search の設定。Transaction Search はアカウント全体の設定で取り込みに課金されるため、このワークショップのためだけに有効化したのなら意識的に無効化してください。
- Workshop Studio のアセットバケット (`ws-assets-us-east-1`)。ご自身のものではありません。
- 有効化した Bedrock のモデルアクセス。

**きれいになったことを確認する。** アカウント全体の認証情報で:

```bash
aws bedrock-agentcore-control list-online-evaluation-configs --region us-east-1 \
  --query 'onlineEvaluationConfigs[].[onlineEvaluationConfigId,status]' --output text

aws bedrock-agentcore-control list-evaluators --region us-east-1 \
  --query 'evaluators[].evaluatorId' --output text | tr '\t' '\n' \
  | grep -E 'TrajectoryCompliance|edd_workshop' || echo "clean: no workshop evaluators left"
```

1 つ目は何も出力しないはずです。2 つ目は `clean: no workshop evaluators left` を出力するはずです。

2 つ目のコマンドは、マネージドなものを除外しようとするのではなく **ご自身の** 評価器名に一致させます。アカウントには予想より多くのマネージド評価器があるからです。`Builtin.*` のファミリーと並んで `ThirdParty.*` のファミリー (`ThirdParty.DeepEval.Bias`、`ThirdParty.DeepEval.Toxicity`、`ThirdParty.AutoEval.Humor` など十数個) があります。これらは AWS が管理しており、常に存在し、あなたが削除するものではないので、素の一覧は決して空にならず、どちらの意味でも何も証明しません。

## ここからどこへ

- **ケースを増やす**。ワークショップの 6 ケースは旅程の制約のごく表面に触れただけです。複数都市の旅程、アクセシビリティの制約、食事エージェントへの食事制限を追加してください。
- **カスタム評価器**。`EvaluatorMode=Custom` とドメイン固有のルーブリックでデプロイしてください。汎用の有用性ではなく、チームの実際の品質基準に対して採点します。
- **複数ジャッジ**。異なるモデルで LLM ジャッジを 2 つ動かし、不一致を浮かび上がらせてください。不一致はシグナルです。
- **既存のエージェントに EDD を適用する**。チームのロードマップにある専門ツールを 1 つ選んでください。配線の Power を適用します。EDD 駆動開発の Power を適用します。両方のレンズが緑の状態で 1 回のイテレーションをリリースします。それが最小で実行可能な導入経路です。

:::alert{type="success" header="自信をもってエージェントを出荷する規律が手に入りました"}
エージェントへのあらゆる変更、新しいモデル、プロンプトの微調整、ツールの追加が、いまやコンテンツとトラジェクトリの両方のレンズにわたって検証可能な前後を持ちます。安全にデプロイしてください。
:::
