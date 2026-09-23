---
title: "3.3 継続的な評価でプロンプトを修正する"
weight: 30
---

**シナリオ。** エージェントが月曜に Grand Museum を訪れるよう提案した、とお客様から報告がありました。追跡するとこうでした。Coordinator が `plan_route` の前に `query_sites` を飛ばしたため、ルートプランナーは月曜休館を知らないままでした。

これが動いている EDD ループです。**変更 → 評価 → 出荷 → 監視を続ける。** ここではその制御された版を実行します。プロンプトを弱めてリグレッションを再現し、評価がそれを捉えるのを見て、修正を戻し、評価がそれを確認するのを見ます。

## ステップ 1: 現在の Coordinator プロンプトを読む

Code Editor の **Explorer** で `travel-agent/src/coordinator.ts` を開きます。すぐ後で同じファイルを編集するので、タブは開いたままにしてください。

`COORDINATOR_SYSTEM_PROMPT` は **すでに強化されたルールで始まっています**。まさにこのインシデントのあとに、以前のエンジニアが投入した修正です。

```ts
ABSOLUTE RULE, NO EXCEPTIONS:
  Before you call plan_route, you MUST first call query_sites for the
  interest categories the user mentioned. Examples:
    - User says "Plan a history-focused trip arriving Monday" → first
      call query_sites(query="history"), see Grand Museum closes
      Monday, only then call plan_route with the constraints applied.
    ...
  No exceptions. No assumptions. Never skip query_sites before plan_route.
```

さらに下の `## Important Rules` の下に、同じ意図が 1 行の抽象的なルールとしても現れます (`Always invoke query_sites BEFORE plan_route ...`)。このステップは *プロンプト冒頭の具体的な版が重要な理由* を扱うので、それを削除し、リグレッションを再現し、戻します。

## ステップ 2: プロンプトを弱める

ステップ 4 で正確に復元できるよう、まずファイルをバックアップします。

:::code{language=bash showCopyAction=true showLineNumbers=false}
cd /workshop/edd-workshop/travel-agent
cp src/coordinator.ts /tmp/coordinator.ts.bak
:::

次に `src/coordinator.ts` を編集し、`COORDINATOR_SYSTEM_PROMPT` の先頭にある **`ABSOLUTE RULE, NO EXCEPTIONS:` ブロック全体を削除** して、`## Important Rules` の下に埋もれた 1 行のルールだけを残します。保存します。

## ステップ 3: 予測してから評価を実行する

具体的なルールが消え、埋もれた 1 行だけが残った状態で、最初に失敗するのはどのケースで、どのレンズ (トラジェクトリかコンテンツか) でしょうか。実行する前に 1 行書き留めてください。

:::code{language=bash showCopyAction=true showLineNumbers=false}
npm run build
npm run eval -- --output results/before_prompt_fix.md
:::

`results/before_prompt_fix.md` を、修正が入った状態のベースライン実行と比較します。1 つだけでなく、6 ケース全体のトラジェクトリ列と平均コンテンツスコアを見てください。

**どのケースが劣化するかは決定的ではありません。** 制約の多いケース (`luminara_2day_history_monday`、`luminara_3day_balanced`) が最も可能性が高いものの、実際の実行では代わりに `luminara_dining_focus` のようなもので失敗することもあります。発見は「あるレンズが赤になり、平均が下がった」であって、「この名前のケースが失敗した」ではありません。

:::alert{type="warning" header="トラジェクトリ列が 6/6 のままの場合"}
Sonnet 4.6 は、埋もれた 1 行だけでも *それでも* `query_sites` を呼ぶことがあるため、1 回の実行では 6/6 を維持しうります。それは失敗した演習ではなく 1 つの発見です。強化はこのモデルにとって **安全マージン** であり、それがどれだけ目に見えて効くかは実行ごとに動きます。

同じエージェント、同じモデルで、プロンプトのみを変数とした実測のペアです。

| | 弱めたプロンプト | ルールを戻した状態 |
|---|---|---|
| スイートのトラジェクトリ | 5/6 | 6/6 |
| スイートの平均コンテンツ | 0.75 | 0.89 |
| `dining_focus`、繰り返し 5 回 | **FLAKY 2/5**、コンテンツ 0.00 〜 0.95 | **STABLE PASS 5/5**、コンテンツ 0.95 〜 1.00 |

どのケースが動いたかに注目してください。シナリオが扱う月曜のケースではなく `luminara_dining_focus` です。1 ケースの 1 回の実行はどちらに転んでもコイントスなので、信じる前に反転を確認しましょう。

```bash
npm run eval -- --case dining_focus --runs 5 --output results/weakened_stability.md
```

*ご自身の* 差分で動いたケースに置き換え、**両方の** プロンプトで実行してください。判定 1 つだけではそのケースがぶれやすいとしか言えませんが、判定のペアなら、その原因がご自身の編集だとわかります。FLAKY という結果は、もっとも本番に近い結末です。弱めたプロンプトはエージェントを壊すのではなく、*信頼できなく* します。一度きりのデモを通過し、その後に実トラフィックの一部で発火する種類のバグです。
:::

## ステップ 4: 修正を戻す

ステップ 2 のバックアップを復元します。

:::code{language=bash showCopyAction=true showLineNumbers=false}
cp /tmp/coordinator.ts.bak src/coordinator.ts
:::

ワークショップのリポジトリのコピーは git のチェックアウトではなくただのディレクトリなので、ここでは `git checkout src/coordinator.ts` は動きません。バックアップを飛ばしてしまった場合は、`COORDINATOR_SYSTEM_PROMPT` の先頭にブロックを手で戻してください。

```ts
const COORDINATOR_SYSTEM_PROMPT = `You are a travel planning coordinator for the fictional city of Luminara. You help users plan multi-day travel itineraries by orchestrating specialist tools.

ABSOLUTE RULE, NO EXCEPTIONS:
  Before you call plan_route, you MUST first call query_sites for the
  interest categories the user mentioned. Examples:
    - User says "Plan a history-focused trip arriving Monday" → first
      call query_sites(query="history"), see Grand Museum closes
      Monday, only then call plan_route with the constraints applied.
    - User says "Plan a 1-day itinerary that includes the Harbor
      Cruise" → first call query_sites(query="Harbor Cruise"), see
      it requires advance booking, only then call plan_route.
  No exceptions. No assumptions.

## Your Capabilities
... (rest of the original prompt) ...
`;
```

リビルドのステップはありません。Coordinator はプロセス開始時に `coordinator.ts` をインポートするので、次の `npm start` か `npm run eval` が新しいプロンプトを取得します。Docker のリビルドも、コンテナイメージの入れ替えも、ECR へのプッシュもありません。型チェックが通ることだけ確認します。

:::code{language=bash showCopyAction=true showLineNumbers=false}
# Confirm tsc still type-checks the file
npm run build
:::

:::alert{type="warning" header="`tsc` がエラーを報告する場合"}
続ける前に構文を直してください。評価の実行も同じファイルをコンパイルします。
:::

**具体が抽象に勝つ理由:** 「Always call query_sites before plan_route」は抽象的です。プロンプト冒頭の版は (興味カテゴリ, 曜日) の組み合わせを厳密に名指しし、2 つの実例を示すので具体的です。その違いを推測ではなく *測定* できるようにするのがトラジェクトリ評価です。出荷されているエージェントは具体的な版を保っており、あなたはいまその理由を証明しました。

## ステップ 5: 修正を戻した状態でフレームワーク評価を実行する (デプロイ前のゲート)

:::code{language=bash showCopyAction=true showLineNumbers=false}
npm run eval -- --output results/after_prompt_fix.md
:::

`results/after_prompt_fix.md` を `results/before_prompt_fix.md` と差分比較します。実測のペアでは、スイートがトラジェクトリ 5/6・平均コンテンツ 0.75 から **6/6 と 0.89** へ動き、回復は 1 ケースに集中していました (`luminara_dining_focus` がコンテンツスコア 0.00 から 0.95 へ)。このゲートの意義はこうです。「このプロンプト編集は効いたのか」に対して、推測ではなく **数値** が手に入りました。

平均だけでなくケースごとの行を読んでください。平均はご自身の編集とは無関係な理由で動きます。`luminara_3day_balanced` だけでも同一コードで 0.25 から 0.90 のどこにでも落ち (3.2 が挙げているのと同じ幅です)、数分差の実行で 0.35 と 0.82 に着地したこともあります。その広がりは、平均の 0.1 のずれを隠したり偽装したりするのに十分です。

![Prompt change before/after](/static/images/module-3/prompt-change-comparison.png)

ここに示している例示的なシグナルは、`dining_focus` でのトラジェクトリ FAIL から PASS への変化で、上の実測のペアが示したものと同じです。

:::alert{type="warning" header="数値が異なる場合、または逆方向に動く場合"}
LLM ジャッジのコンテンツスコアは同一コードでも実行ごとに変動し、Sonnet 4.6 ではプロンプトの修正が入っているかどうかに関わらず 1 回の実行が 6/6 を維持しうります。そうなるとコンテンツ列が差の現れる唯一の場所となり、ジャッジのノイズが上の図と反対方向に押しやることもあります。

修正が何かを劣化させたと決めつけないでください。**同一** コードでの繰り返し実行で確認します。`npm run eval -- --case <name> --runs 5` は、コイントスではなく STABLE/FLAKY の判定を返します。

トラジェクトリは **より** 信頼できるシグナルですが、無敵ではありません。同じコードの 2 回の実行で、毎回異なる 1 ケースが失敗するのを見ることもあります。したがって「両方の実行で 5/6、ただし別のケース」は、編集が何かを壊した証拠ではなく、ぶれやすさの発見です。この 6 ケースのスイートでの目安はこうです。1 回の実行での平均コンテンツの約 0.15 未満の変化は、繰り返し実行が別のことを言うまではノイズであり、1 ケースの反転も `--runs 5` がそうでないと言うまではノイズです。
:::

## ステップ 6: 実トラフィックを生成する (デプロイ後の煙感知器)

Online Eval に、制約の多いクエリの小さなループを流します。`npm start` ではなく、モジュール 1 で選んだパスの **計測済み** エントリポイントを使ってください。

:::alert{type="warning" header="travel-agent/ からの `npm start` はテレメトリーを出しません"}
`npm start` はローカル開発用のエントリポイントです。Bedrock に直接話しかけ、CloudWatch には何もエクスポートしません。その方法で生成したトラフィックは **スパンをゼロ** しか生まないため、Online Eval は採点するものがなく、ステップ 7 はいつまでも空のままです。テレメトリーが配線されているのは、以下の 2 つのエントリポイントだけです。
:::

**Path A (AgentCore Runtime 上の Strands):**

:::code{language=bash showCopyAction=true showLineNumbers=false}
cd /workshop/edd-workshop/travel-agent-strands
for i in 1 2 3 4 5; do
  agentcore invoke "Plan a 2-day Luminara trip arriving Monday with a history focus."
  echo "---"
done
:::

:::alert{type="warning" header="Path A: このトラフィックはデプロイ済みのエージェントから来ており、あなたの編集からではありません"}
ステップ 2 から 5 で編集したのは `travel-agent/src/coordinator.ts` です。ご自身の Runtime が動かしているのは `travel-agent-strands/` で、それは `src/coordinator.py` に独自のプロンプトを持つため、これらの呼び出しは **デプロイされているもの** を動かしており、いま変更したファイルではありません。ステップ 7 は実トラフィックに対する実際のスコアを見せてくれますし、それがループの煙感知器の側面です。ただ、この特定の編集の測定ではありません。

そのずれは回避策ではなく教訓です。プロンプトの変更は、デプロイして初めて本番に入ります。Path A でこれを埋めるには、`travel-agent-strands/src/coordinator.py` に同じ編集を加え、ループを送る前に再デプロイしてください。

```bash
cd /workshop/edd-workshop/travel-agent-strands
agentcore deploy -y      # about 2 minutes
```

Path B ではアダプターが編集した TypeScript のエージェントを動かすので、そのトラフィックはデプロイのステップなしで変更を反映します。
:::

**Path B (任意のフレームワーク、OpenInference アダプター経由):**

:::code{language=bash showCopyAction=true showLineNumbers=false}
cd /workshop/edd-workshop/openinference-aws-adapter
for i in 1 2 3 4 5; do
  USER_QUERY="Plan a 2-day Luminara trip arriving Monday with a history focus." npm start
  echo "---"
done
:::

採点には 15 〜 25 分必要です (AgentCore のセッションアイドルタイムアウト 5 分、その後にジャッジ)。待つ間に、プロンプトの変更が他に何も壊していないことを確認するため、フレームワーク評価を再実行します。

:::code{language=bash showCopyAction=true showLineNumbers=false}
npm run eval -- --output results/regression_check.md
:::

## ステップ 7: Online Eval のスコアを確認する

ヘルパースクリプトが、どちらのパスでも設定とその結果ロググループを代わりに解決します。

:::code{language=bash showCopyAction=true showLineNumbers=false}
cd /workshop/edd-workshop
./scripts/read-eval-scores.sh
:::

生のコマンドを実行したい場合は、ワークショップのすべての設定名が `edd_workshop_` で始まることに注意してください。それが照合すべき文字列です。

:::code{language=bash showCopyAction=true showLineNumbers=false}
EVAL_CFG_ID=$(aws bedrock-agentcore-control list-online-evaluation-configs \
  --region us-east-1 \
  --query 'onlineEvaluationConfigs[?contains(onlineEvaluationConfigName, `edd_workshop`)].onlineEvaluationConfigId | [0]' \
  --output text)

aws logs tail "/aws/bedrock-agentcore/evaluations/results/$EVAL_CFG_ID" \
  --since 30m --format short | head -10
:::

あるいは GenAI Observability ダッシュボードで、エージェントのサービスを開き、**Evaluations** タブへ進みます。

:::alert{type="warning" header="サービス名ではなく `edd_workshop` で照合してください"}
Path A の設定名にはキャメルケースで `travelAgent` が含まれるため、`travel_agent` でのフィルターは何にも一致せず、`EVAL_CFG_ID` は `None` と表示され、コマンドは `aws logs tail .../results/None` になります。このワークショップが作るすべての設定には `edd_workshop_` が前置されており、両方のパスで一致します。

`bedrock-agentcore-control list-online-evaluation-configs` には最近の **AWS CLI v2** も必要です (モジュール 0 のセットアップにあるバージョンの注記を参照)。以前の実行から `edd_workshop` の設定が複数アカウントに残っている場合、`[0]` はデプロイしたものではない可能性があります。`./scripts/read-eval-scores.sh` は、稼働中の設定からロググループを読み取ることで、その推測を回避します。
:::

## 証明したこと

1 つのこと、つまりプロンプトを変更し、そして:

1. **フレームワーク評価がデプロイ前に検証しました**: 劣化したケースでトラジェクトリが回復し、他の場所で新たなリグレッションはありませんでした。
2. **Online Eval がデプロイ後も監視し続けました**: 実トラフィックが自動採点され、手動のオーケストレーションはありません。Path B ではそのスコアが行った編集をカバーします。Path A では、再デプロイしていない限りデプロイ済みの Strands エージェントをカバーします。これがステップ 6 のボックスが示している区別です。

これが EDD ループです。両方のレンズが正の変化で一致することが、デプロイのシグナルです。

:::alert{type="success" header="残る洞察"}
これがエージェントを本番でエンジニアリング可能にするものです。EDD がなければ、あらゆるプロンプト変更は推測です。EDD があれば、あらゆる変更に検証可能な前後があります。
:::

## チェックポイント: 進む前に 3 分

走り書きのファイルに答えてください。モジュール 4 が本番データからループを閉じるときに再利用します。

1. **何を変えたか。** 1 文で。触った唯一の変数です。
2. **何がそれを証明したか。** 厳密な証拠です。どのケースの、どの列が、どのレポートファイルで。
3. **ルールを完成させる:** 「プロンプトを変更するときは、出荷の前に ___ すべきで、リグレッションのシグナルを信じるのは ___ のときだけである。」
4. **職場に戻ったら:** ご自身のシステムのどのプロンプトに ABSOLUTE-RULE の扱いに値する埋もれたルールがあり、それが重要だとどの評価ケースが証明するでしょうか。

3 番の空欄を埋められない場合は、モデル差し替えのページのステップ 7 (安定性レポート) を読み直してください。EDD を、テストを 2 回実行して期待するだけの行為から分けているのがその部分です。

準備ができたら: **[モジュール 3.4: トラジェクトリ評価を AgentCore にデプロイする](../04-online-trajectory-eval/)**。
