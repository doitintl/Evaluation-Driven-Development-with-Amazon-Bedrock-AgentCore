---
title: "3.2 モデルを差し替えてリグレッションを捉える"
weight: 20
---

**シナリオ。** エージェントの推論呼び出しに別のモデルを評価してほしいと依頼されました。レイテンシ、スループット、価格が異なります。エージェントを劣化させずに差し替えられるでしょうか。

EDD は推測ではなく数値で答えます。ここでは Bedrock のモデルを別のものに差し替え、コンテンツとトラジェクトリのスコアが動く様子を観察します。どのモデルを選ぶかは例示にすぎず、要点はワークフローです。

## ステップ 1: ケースを読む

Code Editor の **Explorer** で `travel-agent/eval/cases.ts` を開きます。

6 つのケースが、4 つの一致モードのうち 3 つにわたって制約の範囲をカバーします。`superset` が 4 つ、`in_order` が 1 つ、`subset` が 1 つ、`exact` はなしです (`exact` がエージェントよりパイプラインに向く理由は 3.1 を参照)。ここで興味深いのは `luminara_2day_history_monday` です。

```ts
{
  name: "luminara_2day_history_monday",
  prompt:
    "Plan a 2-day Luminara trip arriving Monday focusing on history. I want to see the Grand Museum and the Royal Palace.",
  expected_trajectory: ["query_sites", "plan_route", "suggest_dining"],
  trajectory_match: "superset",
  rubric:
    "The Grand Museum closes on Monday and the Royal Palace closes on Tuesday. The itinerary MUST schedule the Grand Museum on day 2 (Tuesday) and the Royal Palace on day 1 (Monday), or it MUST explicitly state the closure conflict and offer an alternative day. The response MUST mention that the Royal Palace requires advance booking. The Coordinator MUST NOT schedule the Grand Museum on Monday day 1.",
  // No must_not_contain here, deliberately: see the comment in the file.
}
```

Coordinator は `plan_route` より前に `query_sites` を呼び、ルートプランナーに実際の休館日データを渡さなければなりません。そのルールは `src/coordinator.ts` の `COORDINATOR_SYSTEM_PROMPT` にあります。`query_sites` を飛ばすと、応答が *正しく見えても* ケースは失敗します。

:::alert{type="info" header="`must_not_contain` があった場所のコメントを読んでください: 誤っていたゲート"}
このケースにはかつて `must_not_contain: ["Day 1: Monday", "Monday | Grand Museum"]` が付いていて、**正しい** 回答すべてで失敗していました。エージェントは旅程を `=== Day 1: Monday ===` として描画し、月曜に到着するなら 1 日目は本当に月曜なので、最初の文字列は良い出力に一致してしまいます。2 つ目は何にも一致しえませんでした。日付の見出しと観光地の行が別の行にあり、ゲートは素朴な部分文字列テストだからです。

そのゲートが狙っていた制約 (「Grand Museum は月曜の見出しの下に現れてはならない」) は **構造** に関するもので、部分文字列では表現できません。そのためルーブリックに置き、ジャッジが旅程全体を見られるようにしています。`must_not_contain` は、それ単体で明らかに誤っている文字列のために残し、位置に関わるものはルーブリックに担わせてください。正しい出力で発火するゲートは、ゲートがないより悪いものです。失敗を無視する習慣を植えつけます。
:::

## ステップ 2: ベースラインのモデルを確認する

Coordinator はシェルがエクスポートした `MODEL_ID` を使います。Code Editor はログイン時に `config.env` を読み込み、`MODEL_ID=us.anthropic.claude-sonnet-4-6` を設定します。

:::code{language=bash showCopyAction=true showLineNumbers=false}
echo "MODEL_ID=$MODEL_ID"
:::

## ステップ 3: ベースラインの評価を実行する

コマンドを再現可能にするため、Sonnet 4.6 を明示的に固定します。

:::code{language=bash showCopyAction=true showLineNumbers=false}
MODEL_ID=us.anthropic.claude-sonnet-4-6 npm run eval -- --output results/baseline_sonnet.md
:::

約 3 〜 5 分かかります (6 ケース x 各約 30 秒、加えて LLM ジャッジの採点)。`results/baseline_sonnet.md` を開きます。トラジェクトリの合格率 6/6、平均コンテンツスコア 0.85 〜 0.95 程度を見込んでください。

ベースラインでときどき 5/6 になるのはサンプリングノイズであり、セットアップの不備ではありません。同一コードでベースラインを繰り返し実行すると、およそ 5 回に 1 回はどれか 1 ケースがぶれ、`luminara_3day_balanced` のコンテンツだけでも 0.25 から 0.90 までの測定値が出ています。この 2 つの極端な値は **同じモデル、同じコード、15 分差** で出たものなので、1 回の実行の 1 つの数値からわかることはごくわずかです。だからこそステップ 7 では、結論を出す前にケースを再実行します。数値は指紋ではなく分布として扱ってください。

スコアボードではなくエンジニアとして読みましょう。問いは 2 つです。

1. `luminara_2day_history_monday` について `Trajectory actual` の行を見つけます。**最初に** 実行されたのはどのツールで、ここでその順序が重要な理由は何でしょうか。(答え: `query_sites`。`plan_route` に休館日データを渡すのがそれだからです。この因果の連鎖こそトラジェクトリのレンズが守るものです。)
2. 最も低いコンテンツスコアを見つけ、ジャッジの理由を読みます。**特定のルーブリック条項** を挙げているでしょうか、それとも曖昧でしょうか。この理由の文字列が、このモジュールの残りにおけるデバッグの手がかりになります。

このレポートが **変更前の状態** です。以下のすべての結論はそれとの差分です。ベースラインがなければ「リグレッション」は単なる意見にすぎません。

:::alert{type="info" header="仕組み: 1 つのレポートに 2 つの評価器がある理由"}
`run-experiment.ts` はケースごとに両方を並列で実行します。`judge.ts` の LLM ジャッジが応答のコンテンツを採点し、`trajectory.ts` のマッチャーが `agent.state.messages` から抽出したツール呼び出し順序を採点します。
:::

:::alert{type="info" header="任意: us.* プレフィックスの意味"}
`us.anthropic.claude-sonnet-4-6` (およびこのモジュールのすべての `us.amazon.*` id) の `us.` プレフィックスは、US 地域向けの [Amazon Bedrock クロスリージョン推論プロファイル](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html) です。Bedrock は InvokeModel の呼び出しを、容量のある US リージョン (`us-east-1`、`us-east-2`、`us-west-2`) に振り分けます。だから 3 つすべてで動作します。AP や EU のリージョンでは `us.` を `apac.` または `eu.` に置き換えてください (例: `eu.anthropic.claude-sonnet-4-6`)。

travel-agent の TS 側のフォールバック (`src/utils/config.ts`) も `us.anthropic.claude-sonnet-4-6` です。環境変数が優先されます。
:::

## ステップ 4: 別のモデルに差し替える

`MODEL_ID` は呼び出しごとに読まれるため、リビルドもデプロイのステップも不要です。レンズの違いが見えるよう、Sonnet 4.6 とサイズやファミリーが有意に異なるモデルを選びます。

:::code{language=bash showCopyAction=true showLineNumbers=false}
MODEL_ID=amazon.nova-lite-v1:0 npm start -- "Plan a 2-day Luminara trip arriving Monday focusing on history."
:::

:::alert{type="info" header="任意: 代わりに使える他の候補モデル"}
`amazon.nova-pro-v1:0`、`us.anthropic.claude-haiku-4-5-20251001-v1:0`、あるいはお使いのアカウントから到達できる他の Bedrock チャットモデルでもかまいません。重要なのは **候補** が **ベースライン** と異なることだけです。pi-ai でのプレフィックスに注意してください。Amazon のモデルは `amazon.`、Anthropic のモデルは `us.anthropic.` を使います。
:::

## ステップ 5: 予測してから評価を再実行する

まず 2 つの予測を書き留めます。走り書きのファイルで十分です。予測にコミットすることが、結果を印象づけます。

1. 軽量モデルの **トラジェクトリ** 合格率は 6/6 より高くなるでしょうか、低くなるでしょうか、同じでしょうか。理由は。
2. **平均コンテンツ** スコアはベースラインより高くなるでしょうか、低くなるでしょうか。理由は。

ほとんどの人は「すべてが悪化する」と予測します。実際の結果はもっと興味深く、予測が外れることこそが学びです。

:::code{language=bash showCopyAction=true showLineNumbers=false}
MODEL_ID=amazon.nova-lite-v1:0 npm run eval -- --output results/candidate.md
:::

`results/candidate.md` を開き、読み進める前に両方の予測を数値と照らし合わせます。典型的な比較です。

![Model swap comparison](/static/images/module-3/model-swap-comparison.png)

再現性のある発見はこうです。6 ケースのどこかで、2 つの列が **反対方向** に動きます。軽量モデルは、より易しいケースではコンテンツで *高い* スコアを出しうる一方 (簡潔さは率直さとして読まれます)、制約の多いケースではトラジェクトリを劣化させます。トラジェクトリのレンズがなければ、コンテンツだけでは見えないリグレッションをそのまま出荷することになります。

:::alert{type="warning" header="実行結果が図と一致しない場合"}
どのケースが失敗するか、そしてどの機構で失敗するか (ツール呼び出しのスキップか、ツール順序の違いか、コンテンツのみか) は **決定的ではありません**。同じ差し替えを再実行すると別のケースが浮上することもあり、トラジェクトリではなくコンテンツのみのリグレッションが出ることもあります。例示しているのは `luminara_2day_history_monday` で、小さなモデルが `query_sites` を飛ばして `plan_route` に直行しうるケースですが、正しいと言うためにご自身の実行がそれを再現する必要はありません。
:::

## ステップ 6: 2 つのレポートを並べて比較する

:::code{language=bash showCopyAction=true showLineNumbers=false}
# Baseline
MODEL_ID=us.anthropic.claude-sonnet-4-6 npm run eval -- --output results/before.md

# Candidate
MODEL_ID=amazon.nova-lite-v1:0 npm run eval -- --output results/after.md

# Diff (review the two runs side-by-side)
diff results/before.md results/after.md
:::

視覚的な差分を見るには、Code Editor の **Explorer** で `results/*.md` の両ファイルを選択し、**右クリック → Compare Selected** を使います。

## ステップ 7: リグレッションが本物か確認する

1 ケースの 1 回の実行は 1 つのサンプルであり、判定ではありません。6 ケースのスイートでは平均コンテンツの変化が約 0.15 未満ならジャッジのノイズの範囲内で、トラジェクトリの 1 回の反転はコイントスでありえます。業界の慣行 (τ-bench の pass^k、Anthropic の評価ガイダンス) は、行動に移す前に疑わしいケースを数回再実行することです。

差分で最も動いたケースを取り、候補モデルでそのケースだけを 5 回再実行します。

:::code{language=bash showCopyAction=true showLineNumbers=false}
MODEL_ID=amazon.nova-lite-v1:0 npm run eval -- --case 2day_history --runs 5 --output results/confirm_candidate.md
:::

各実行は結果が出るたびに自身の `traj=`/`score=` 行を出力し、軽量モデルなら全体が数分で終わります。

`--case` には *ご自身の* 差分で動いたケースの部分文字列を入れてください。安定性レポートを開き、判定の行を読みます。

- **STABLE FAIL (0/5)**: リグレッションは本物です。実行ごとの詳細は毎回同じツールが欠けていることを示すので、運ではなく挙動です。
- **STABLE PASS (5/5)**: 最初の候補実行はサンプリングノイズに当たったということです。何かを結論づける前に、ベースラインも同じ方法で再実行してください。
- **FLAKY (2/5、3/5 ...)**: 最も示唆に富む結果です。ベースラインが安定していたケースで、候補が *敏感* だということです。本番ではこれはトラフィックの一部で発火する潜在的インシデントであり、スモークテストを通過して午前 2 時に呼び出しをかけてくるので、安定した失敗よりむしろ悪いとも言えます。

:::alert{type="success" header="いま起きたこと: 因果の連鎖"}
1. **あなたの行動**: 変数をちょうど 1 つ (`MODEL_ID`) だけ変え、他は変えませんでした。
2. **機構**: 軽量モデルはプロンプトの「`plan_route` より前に `query_sites` を呼ぶ」というルールの遵守が不確かなので、一部のサンプルでは休館日データなしで計画します。
3. **証拠**: 安定性レポートの `Trajectory actual` の行です。失敗した実行のツール一覧を、成功した実行のものと比べてください。
4. **ルール**: リグレッションは、*同じ入力の繰り返し実行にわたって安定して* いるときに確認され、*変数が 1 つだけ変わった* ときに帰属できます。1 回の実行は証拠ではなく、1 つの変更が帰属です。

**反証チェック:** モデルを差し替えつつ **同時に** プロンプトも編集していたら、このレポートはどの変更が失敗を引き起こしたかについて何を教えてくれるでしょうか。(何も。だからこそこのループは変更の積み重ねを禁じています。)
:::

## 判断

`--runs` で安定性を確認したあと、差分は次の 3 つのパターンのいずれかを示します。

1. **両方の列が改善するか横ばい**: 候補は実用的な置き換えです。予期しなかったクエリのための煙感知器として、Online Eval は動かし続けてください。
2. **コンテンツは改善、トラジェクトリは劣化**: デプロイしないでください。候補は Coordinator のシステムプロンプトの規律に従っておらず、応答だけではそれを示せません。
3. **トラジェクトリは維持、コンテンツは劣化**: 候補にもっと手がかりを与えるようプロンプトを締め、再実行してください。

両方のレンズが緑になれば、モデル選択は通常のコスト / レイテンシ / 品質のトレードオフになります。その判断を責任をもって行うためのデータを与えるのが、評価のスキャフォールドです。現在のトークン単価は [Amazon Bedrock の料金ページ](https://aws.amazon.com/bedrock/pricing/) にあります。

単一の数値 (「良くなったか」) は、何が劣化しているかを隠します。それがこのワークショップの核心の教訓です。EDD は問いを 2 つのレンズに分け、それぞれに対する判断を求めます。

## ステップ 8: 次のモジュールの前に戻す

:::code{language=bash showCopyAction=true showLineNumbers=false}
unset MODEL_ID
:::

次の `npm start` または `npm run eval` は、`config.env` から既定の Sonnet 4.6 推論プロファイルを再び取得し、なければ `src/utils/config.ts` にフォールバックします。

準備ができたら: **[モジュール 3.3: プロンプト変更](../03-prompt-change/)**。
