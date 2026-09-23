---
title: "3.4 トラジェクトリ評価を AgentCore にデプロイする"
weight: 40
---

**シナリオ。** `npm run eval` は、開発者が思い出して実行したときにしか動きません。`Builtin.Helpfulness` がすでにコンテンツを採点しているのと同じように、すべての本番セッションを自動でトラジェクトリ検査し、`query_sites` の呼び出しが飛ばされ始めた瞬間に知りたいとします。

AgentCore の **Custom Code-Based Evaluator** は、セッションのスパンを受け取って判定を返す Lambda 関数です。それが `trajectory.ts` のロジックを本番トラフィックにデプロイする方法です。

:::alert{type="success" header="持ち帰るべき 1 つの考え: 同じマッチャーを、今度は無人で"}
デプロイ前のトラジェクトリ検査が、意味を変えずにデプロイ後の検査になります。このページの後は、両方のレンズがすべてのセッションを自動採点します。コンテンツはマネージドな LLM ジャッジが、トラジェクトリはご自身のコードが採点します。
:::

## 仕組み

すでに 1 つの評価器が動いています。ここではその横に、種類の異なる 2 つ目を追加します。

| | モジュール 2 の評価器 | ここで追加するもの |
|---|---|---|
| **評価器** | `Builtin.Helpfulness`、マネージドな LLM ジャッジ | Custom Code-Based Evaluator、ご自身の Lambda |
| **読むもの** | エージェントレコードの入力と出力のテキスト | `sessionSpans`、トレース内のすべてのスパン |
| **問うこと** | 「回答は有用だったか」 | 「エージェントは正しいツールを呼んだか」 |
| **返すもの** | 0.0 〜 1.0 のスコア | PASS または FAIL |
| **ロジックの所在** | ルーブリックとモデル | コードとしての `trajectory.ts` マッチャー |

どちらもすべてのセッションで動き、どちらの結果も同じ評価用ロググループに届きます。2 つのレンズが自動化され、ループに人間はいません。

## ステップ 1: Lambda 関数を書く

Lambda は `sessionSpans` を受け取ります。X-Ray で見たのと同じスパンデータです。そして判定を返します。ここでは `superset` の検査を実装します。`query_sites`、`plan_route`、`suggest_dining` がすべて、順序は問わず、追加も許して現れなければなりません。

:::code{language=bash showCopyAction=true showLineNumbers=false}
cd /workshop/edd-workshop
mkdir -p lambda/trajectory-evaluator
:::

:::code{language=bash showCopyAction=true showLineNumbers=false}
cat > lambda/trajectory-evaluator/index.py << 'EOF'
"""
Custom Code-Based Evaluator: Trajectory Compliance
Checks that the agent called all expected tools (superset mode).
"""

EXPECTED_TOOLS = ["query_sites", "plan_route", "suggest_dining"]


def handler(event, context):
    """
    Input: event with evaluationInput.sessionSpans
    Output: {label, value, explanation}
    """
    spans = event.get("evaluationInput", {}).get("sessionSpans", [])
    
    # Extract tool names from spans
    # Span names follow the pattern "execute_tool {tool_name}" (strands) 
    # or "tool: {tool_name}" (openinference)
    actual_tools = []
    for span in spans:
        name = span.get("name", "")
        if name.startswith("execute_tool "):
            actual_tools.append(name.replace("execute_tool ", ""))
        elif name.startswith("tool: "):
            actual_tools.append(name.replace("tool: ", ""))
    
    # Superset check: all expected tools must appear at least once
    missing = [t for t in EXPECTED_TOOLS if t not in actual_tools]
    
    if not missing:
        return {
            "label": "PASS",
            "value": 1.0,
            "explanation": (
                f"Trajectory compliant. Agent called all expected tools: "
                f"{', '.join(EXPECTED_TOOLS)}. "
                f"Actual sequence: {' → '.join(actual_tools)}"
            )
        }
    else:
        return {
            "label": "FAIL",
            "value": 0.0,
            "explanation": (
                f"Trajectory violation. Missing tools: {', '.join(missing)}. "
                f"Expected: {', '.join(EXPECTED_TOOLS)}. "
                f"Actual: {' → '.join(actual_tools) if actual_tools else '(no tools called)'}"
            )
        }
EOF
:::

:::alert{type="info" header="仕組み: LLM-as-Judge ではなく Lambda にする理由"}
トラジェクトリの一致は決定的です。「ツール X はスパン一覧に現れたか」には、与えられたスパン集合に対してちょうど 1 つの正解があります。LLM ジャッジはトークンを消費し、エージェントがすでに持つばらつきの上にさらに非決定性を足すことになります。この Lambda は約 50ms で動き、コストはほぼゼロです。ジャッジのトークンは、判断が本当に必要なコンテンツ品質のために取っておきましょう。
:::

## ステップ 2: Lambda をデプロイする

:::code{language=bash showCopyAction=true showLineNumbers=false}
cd /workshop/edd-workshop/lambda/trajectory-evaluator

# Package
zip trajectory-evaluator.zip index.py

# Create execution role
aws iam create-role \
  --role-name trajectory-evaluator-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }' \
  --region us-east-1

aws iam attach-role-policy \
  --role-name trajectory-evaluator-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Wait for role propagation
sleep 10

# Create Lambda function
aws lambda create-function \
  --function-name edd-trajectory-evaluator \
  --runtime python3.12 \
  --handler index.handler \
  --role arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/trajectory-evaluator-role \
  --zip-file fileb://trajectory-evaluator.zip \
  --timeout 60 \
  --region us-east-1
:::

期待される出力の抜粋です (`create-function` は設定全体を出力します)。
```json
{
    "FunctionName": "edd-trajectory-evaluator",
    "FunctionArn": "arn:aws:lambda:us-east-1:ACCOUNT:function:edd-trajectory-evaluator",
    "Runtime": "python3.12",
    "Handler": "index.handler",
    "State": "Pending",
    "StateReason": "The function is being created.",
    "StateReasonCode": "Creating"
}
```

ここでの `State: Pending` は正しい状態です。`create-function` は関数のプロビジョニング完了を待たずに返ります。数秒で `Active` に変わり、次のステップは `Active` になっているのを必要としません。

## ステップ 3: AgentCore に評価器を登録する

Lambda を `TRACE` レベルのコードベース評価器として登録し、その id を次のステップのために保存します。

:::code{language=bash showCopyAction=true showLineNumbers=false}
LAMBDA_ARN=$(aws lambda get-function \
  --function-name edd-trajectory-evaluator \
  --query 'Configuration.FunctionArn' --output text \
  --region us-east-1)

cat > /tmp/traj_evaluator_config.json <<JSON
{
  "codeBased": {
    "lambdaConfig": {
      "lambdaArn": "$LAMBDA_ARN",
      "lambdaTimeoutInSeconds": 60
    }
  }
}
JSON

TRAJ_EVALUATOR_ID=$(aws bedrock-agentcore-control create-evaluator \
  --region us-east-1 \
  --evaluator-name TrajectoryCompliance \
  --level TRACE \
  --description 'Checks that the agent called query_sites, plan_route, and suggest_dining (superset mode).' \
  --evaluator-config file:///tmp/traj_evaluator_config.json \
  --query 'evaluatorId' --output text)

echo "$TRAJ_EVALUATOR_ID" > /tmp/traj_evaluator_id.txt
echo "Trajectory evaluator: $TRAJ_EVALUATOR_ID"
:::

期待される出力は、次の形の id です。
```
Trajectory evaluator: TrajectoryCompliance-XXXXXXXXXX
```

:::alert{type="info" header="仕組み: boto3 ではなく AWS CLI を使う理由"}
Code Editor には `boto3` も、それをインストールする `pip` も入っていないため、このモジュールのすべての AgentCore 呼び出しは `aws bedrock-agentcore-control` を通します。`--evaluator-config` のドキュメントは API と同じメンバー名 (`codeBased.lambdaConfig.lambdaArn`、`lambdaTimeoutInSeconds`) を使うので、同等の SDK 呼び出しの直訳になっています。
:::

## ステップ 4: Online Evaluation Config に評価器を追加する

モジュール 2 の設定はコンテンツジャッジを 1 つ動かしています。両方がすべてのセッションで動くよう、トラジェクトリ評価器をその **横に** アタッチします。

送信する評価器の一覧は以前の一覧を **置き換える** ため、下のコマンドはすでにアタッチされているものを読み、それに追加します。ジャッジの id をハードコードしないでください。任意のページ 2.6 を実施した場合、アタッチされているジャッジは `Builtin.Helpfulness` ではなくご自身のカスタムルーブリックであり、ハードコードすると黙ってそれを外してしまいます。

:::code{language=bash showCopyAction=true showLineNumbers=false}
source /workshop/edd-workshop/config.env

TRAJ_EVALUATOR_ID=$(cat /tmp/traj_evaluator_id.txt)

EVAL_CFG_ID=$(aws bedrock-agentcore-control list-online-evaluation-configs \
  --region us-east-1 \
  --query 'onlineEvaluationConfigs[?contains(onlineEvaluationConfigName, `edd_workshop`)].onlineEvaluationConfigId | [0]' \
  --output text)

echo "Found evaluation config: $EVAL_CFG_ID"

# Whatever judge is attached today (Builtin.Helpfulness, or your 2.6 custom rubric)
EXISTING=$(aws bedrock-agentcore-control get-online-evaluation-config \
  --region us-east-1 \
  --online-evaluation-config-id "$EVAL_CFG_ID" \
  --query 'evaluators[].evaluatorId' --output text)

echo "Already attached: $EXISTING"

# Rebuild the list: everything that was there, plus the trajectory evaluator
EVAL_ARGS=""
for id in $EXISTING; do
  [ "$id" = "$TRAJ_EVALUATOR_ID" ] && continue   # keep it idempotent
  EVAL_ARGS="$EVAL_ARGS evaluatorId=$id"
done

aws bedrock-agentcore-control update-online-evaluation-config \
  --region us-east-1 \
  --online-evaluation-config-id "$EVAL_CFG_ID" \
  --evaluators $EVAL_ARGS evaluatorId="$TRAJ_EVALUATOR_ID"
:::

両方の評価器がアタッチされたことを確認します。

:::code{language=bash showCopyAction=true showLineNumbers=false}
aws bedrock-agentcore-control get-online-evaluation-config \
  --region us-east-1 \
  --online-evaluation-config-id "$EVAL_CFG_ID" \
  --query 'evaluators[].evaluatorId' --output text
:::

期待される結果は、コンテンツジャッジと `TrajectoryCompliance-XXXXXXXXXX` の id が並ぶことです。例:

```
Builtin.Helpfulness    TrajectoryCompliance-JiOdJm8J7D
```

ページ 2.6 を実施した場合は次のようになります。

```
TrajectoryCompliance-JiOdJm8J7D    edd_workshop_travel_quality-UWzZhe44WU
```

:::alert{type="info" header="仕組み: これは部分更新で、サンプリングとロググループの設定は残ります"}
`--evaluators` だけを送ることは、設定の残りを空にしません。`rule` (サンプリングレートとセッションタイムアウト) と `dataSourceConfig.cloudWatchLogs` (ロググループと `serviceNames`) は手を付けられずに残り、設定は `ACTIVE` のままです。

評価器の一覧だけが例外で、こちらは丸ごと置き換えられます。だからステップ 4 はまず現在の一覧を読むのです。上の出力に `TrajectoryCompliance-...` しか見えない場合、コンテンツジャッジが外れています。ブロックを再実行すれば `$EXISTING` から復元されます。
:::

:::alert{type="warning" header="EVAL_CFG_ID が None と表示される場合"}
`edd_workshop` を含む設定名がなかったということです。すべてを一覧して自分のものを選び (名前にご自身の `SERVICE_NAME` が含まれます)、その id で更新を再実行してください。

```bash
aws bedrock-agentcore-control list-online-evaluation-configs \
  --region us-east-1 \
  --query 'onlineEvaluationConfigs[].[onlineEvaluationConfigName,onlineEvaluationConfigId]' \
  --output table
```
:::

:::alert{type="warning" header="Lambda の権限に関する ValidationException で更新が失敗する場合"}
AgentCore Online Eval は、コードベースの評価器を呼び出すために eval 実行ロール (`<ProjectName>-eval-exec`、モジュール 2 の `edd-eval-and-obs` スタックが作成) を引き受けます。権限がないとこうなります。

```
ValidationException: The execution role provided for this Evaluation does not have
permission to access the specified Lambda functions ...
```

**Lambda の既定の名前 (`edd-trajectory-evaluator`) を維持している限り**、ワークショップの CFN スタックがこれを付与済みです。ロールの `InvokeCodeBasedEvaluatorLambda` ステートメントは `edd-trajectory-evaluator*` と `<ProjectName>-*` にスコープされています。Lambda の名前を変えた場合は、権限を明示的に追加してください (`ProjectName` の既定は `edd-workshop`)。

```bash
source /workshop/edd-workshop/config.env
EVAL_ROLE_NAME="edd-workshop-eval-exec"   # = <ProjectName>-eval-exec
aws iam put-role-policy \
  --role-name "$EVAL_ROLE_NAME" \
  --policy-name LambdaInvoke \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [{
      \"Effect\": \"Allow\",
      \"Action\": [\"lambda:InvokeFunction\", \"lambda:GetFunction\"],
      \"Resource\": \"$LAMBDA_ARN\"
    }]
  }"
# IAM changes take a few seconds to propagate; if the update below still
# fails with the permission error, wait ~15s and retry.
```
:::

## ステップ 5: トラフィックを生成してトラジェクトリスコアを確認する

モジュール 1 で選んだパスの **計測済み** エントリポイントを使ってください。`travel-agent/` からの `npm start` はローカル開発用のエントリポイントで、スパンを出さないため、評価器はそのセッションを見ることができません。

**Path A (AgentCore Runtime 上の Strands):**

:::code{language=bash showCopyAction=true showLineNumbers=false}
cd /workshop/edd-workshop/travel-agent-strands
agentcore invoke "Plan a 2-day Luminara trip arriving Monday with a history focus."
:::

**Path B (任意のフレームワーク、OpenInference アダプター経由):**

:::code{language=bash showCopyAction=true showLineNumbers=false}
cd /workshop/edd-workshop/openinference-aws-adapter
USER_QUERY="Plan a 2-day Luminara trip arriving Monday with a history focus." npm start
:::

セッションのアイドルタイムアウトと評価のために 20-25 分見込んでください。ジャッジのキューの負荷により、アイドルタイムアウトの計算から予想される時間を超えることがあるため、15 分で何も見えないことは失敗を意味しません。その後スコアを読みます。

:::code{language=bash showCopyAction=true showLineNumbers=false}
cd /workshop/edd-workshop
./scripts/read-eval-scores.sh
:::

期待される出力です。2 つのスケールは比較できないため、評価器ごとにグループ化されます。
```
  TrajectoryCompliance (1 score(s))
    session abc123def4560a         score=1.0    PASS
      Trajectory compliant. Agent called all expected tools: query_sites, plan_route, suggest_dining.

  Builtin.Helpfulness (1 score(s))
    session abc123def4560a         score=0.83   Very Helpful
      The user requested a 2-day history-focused trip arriving Monday...

  2 score(s) across 2 evaluator(s)
```

任意のページ 2.6 を実施した場合、2 つ目のグループは `Builtin.Helpfulness` ではなくご自身のルーブリック (`edd_workshop_travel_quality`、1-5 スケール) になります。いずれにせよ 2 つのグループが見えるはずです。コンテンツスコアが 1 つ、トラジェクトリの判定が 1 つです。

両方の評価器が同じセッションで動きました。2 つのスコア、2 つのレンズ、完全な自動化です。

**期待される結果: カスタム評価器が実セッションを採点します。** `TrajectoryCompliance` は準拠したセッションで `PASS` (1.0) を返し、一致したツールを挙げた説明を添えます。

![期待される結果: カスタムの TrajectoryCompliance 評価器が実セッションを評価結果ロググループで PASS (1.0) と採点し、一致したツール query_sites、plan_route、suggest_dining を挙げた説明が添えられている](/static/images/module-3/online-trajectory-pass.png)

:::alert{type="warning" header="結果が空で返る場合"}
`Builtin.Helpfulness` だけが現れるのは、トラジェクトリ評価器が動かなかったということです。ステップ 4 で **両方の** 評価器 id がアタッチされたか再確認してください。まったく何もない場合は、待ち時間がまだ終わっていないだけです。
:::

## ステップ 6: トラジェクトリのレンズが失敗を捉えることを証明する

エージェントがルートを計画したり観光地を調べたりする理由がないほど範囲の狭いクエリを送ります。ここでも計測済みのエントリポイントを使ってください。

**Path A (AgentCore Runtime 上の Strands):**

:::code{language=bash showCopyAction=true showLineNumbers=false}
cd /workshop/edd-workshop/travel-agent-strands
agentcore invoke "Suggest dinner near the Royal Palace"
:::

**Path B (任意のフレームワーク、OpenInference アダプター経由):**

:::code{language=bash showCopyAction=true showLineNumbers=false}
cd /workshop/edd-workshop/openinference-aws-adapter
USER_QUERY="Suggest dinner near the Royal Palace" npm start
:::

食事だけのクエリでは、エージェントは通常 `suggest_dining` だけを呼び、グローバルな `superset` ルールが求めるよりツールが少なくなります。再び 20-25 分待ち、ステップ 5 の確認を再実行します。FAIL を見込んでください。

```
  TrajectoryCompliance (4 score(s))
    session 7292da58-2b5d-40dc-91f  score=0.0    FAIL
      Trajectory violation. Missing tools: query_sites, plan_route.
      Expected: query_sites, plan_route, suggest_dining. Actual: suggest_dining
    session a1d63961-7129-4b33-817  score=1.0    PASS
      Trajectory compliant. Agent called all expected tools: query_sites,
      plan_route, suggest_dining. Actual sequence: query_sites → query_sites →
      plan_route → suggest_dining
```

先ほどの準拠したセッションは同じ出力の中で `PASS` のまま残り、それが対比を読みやすくします。1 つの評価器、1 つのルール、2 つの判定です。

同じセッションのコンテンツスコアを確認してください。次のどちらも妥当な結果です。

- **赤/緑**: コンテンツは依然として良いスコアで (食事の回答はそれ自体もっともらしく読めます)、トラジェクトリだけが飛ばされた制約チェックを捉えます。モジュール 3.5 のフレームワークに従えば、トラジェクトリの問題を個別に調査します。
- **赤/赤**: コンテンツも下がります。`query_sites` のデータがないと、回答は注意深いジャッジが指摘する作り話の細部に頼るからです。両方のレンズが一致します。出荷前に差し戻すか修正してください。こちらのほうが強い実証とも言えます。コンテンツ品質が、たいていはそう見えるとしても、トラジェクトリ検査の信頼できる代替にはならないことを示すからです。

見えたものをそのまま報告してください。ここに固定の台本はありません。

:::alert{type="info" header="任意: 食事だけのクエリは本当にトラジェクトリで失敗すべきか"}
それはご自身のビジネスルール次第です。ステップ 3.1 の `subset` モードは反対のことを主張します。範囲の限られた食事のみの依頼 (`luminara_dining_only_scoped` ケース) では、`suggest_dining` **だけ** を呼ぶのが正しいのです。エージェントは過剰に計画すべきではないからです。

そこから実際の設計上の判断が浮かびます。本番のトラジェクトリ評価器には、1 つのグローバルな期待ではなく、クエリごとの期待トラジェクトリ (グラウンドトゥルース) が必要です。モジュール 4 では、本番の例をグラウンドトゥルースのケースに引き込む方法を示します。グローバルな `superset` 検査は妥当な出発点です。制約の多いクエリで `query_sites` を飛ばすという、最も危険な失敗モードを捉えるからです。
:::

## 構築したもの

| このステップの前 | このステップの後 |
|-----------------|-----------------|
| トラジェクトリ評価は開発者がローカルで `npm run eval` を実行したときにだけ動く | トラジェクトリ評価が **すべての本番セッション** で自動的に動く |
| コンテンツ品質は継続的に採点される (Builtin.Helpfulness) | コンテンツ品質とトラジェクトリ遵守の両方が継続的に採点される |
| トラジェクトリの失敗はデプロイ前の 6 テストケースでしか捉えられない | トラジェクトリの失敗が本番クエリの全分布で捉えられる |

`npm run eval` は特定のケースに対するデプロイ前のゲートのままです。オンラインの評価器は、予期しなかったクエリに対するデプロイ後の安全網です。

:::alert{type="info" header="任意: 本番向けに評価器を拡張する"}
ご自身の Lambda は固定の `EXPECTED_TOOLS` 一覧を検査します。本番では次を検討してください。

1. **クエリごとのグラウンドトゥルース**: 期待トラジェクトリを `evaluationReferenceInputs` として渡す ([グラウンドトゥルースに関する AWS ドキュメント](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-based-evaluators.html) を参照)
2. **複数のモード**: 制約の多いクエリには `in_order`、範囲の限られたものには `subset`
3. **ツール呼び出しの頻度**: 空回りへのアラート (`query_sites` の呼び出しが 5 回を超えるのは混乱を示唆します)
4. **LLM-as-Judge のハイブリッド**: `{expected_tool_trajectory}` と `{actual_tool_trajectory}` のプレースホルダーを使う LLM ジャッジのカスタム評価器で、軽微な逸脱を許容するニュアンスのある採点をする
:::

準備ができたら: **[モジュール 3.5: サマリー](../05-summary/)**。
