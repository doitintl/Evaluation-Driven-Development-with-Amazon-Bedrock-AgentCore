---
title: "3.1 2 つのレンズによる評価モデル"
weight: 10
---

## トラジェクトリ一致とは

「3 日間の旅行を計画して」と頼まれた Luminara の Coordinator は、3 つのツールを順に呼ぶべきです。

1. `query_sites`: 観光地とその制約を調べる
2. `plan_route`: 営業日と予約要件を尊重した旅程を作る
3. `suggest_dining`: 計画した立ち寄り先の近くのレストランを追加する

そのツール呼び出しの順序が *トラジェクトリ* です。トラジェクトリ評価は、最終的な回答の読み味ではなく、エージェントがたどった経路を確認します。モジュール 1 (Path B) では、同じトラジェクトリを X-Ray のスパンとして示しました。各 `llm-call-N` が推論ステップ、各 `execute_tool X` がアクションです。

![X-Ray span list showing agent trajectory](/static/images/1f-xray-span-list.png)

## 4 つの一致モード

これらのモードは [Strands](https://strandsagents.com/docs/user-guide/evals-sdk/evaluators/trajectory_evaluator/)、[AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/evaluators-builtin.html)、[LangSmith](https://docs.langchain.com/langsmith/trajectory-evals) の規約に揃えてあります。

| モード | 意味 | 使う場面 | 業界での同等物 |
|------|---------|----------|---------------------|
| `superset` | 期待されるツールがすべて 1 回以上呼ばれた (追加は可) | 順序は問わず、網羅性だけが必要なとき | Strands `any_order`、AgentCore `TrajectoryAnyOrderMatch`、LangSmith Superset |
| `in_order` | 期待されるツールが部分列として現れる (間の追加は可) | 依存関係の順序が重要なとき (sites → route → dining) | Strands `in_order`、AgentCore `TrajectoryInOrderMatch` |
| `exact` | ツール呼び出しの順序が期待と完全一致。追加も並べ替えもなし | 厳格な準拠が必要なとき (安全性が重要な経路) | Strands `exact_match`、AgentCore `TrajectoryExactOrderMatch`、LangSmith Strict |
| `subset` | エージェントが期待される集合のツールのみを呼ぶ。想定外のツールは不可 | 過剰な計画がリグレッションとなる、範囲の限られた依頼 | LangSmith Subset |

1 つの実際の順序に対して、4 つの判定。

```
Expected: [query_sites, plan_route, suggest_dining]
Actual:   [query_sites, query_sites, plan_route, suggest_dining, suggest_dining]

  superset:  PASS ✓  (all expected present)
  in_order:  PASS ✓  (q_s before p_r before s_d)
  exact:     FAIL ✗  (extra calls)
  subset:    PASS ✓  (every call is an expected tool; repeats are allowed)
```

繰り返しに異議を唱えるのは `exact` だけです。**`subset` はどのツールかを問うもので、何回かは問いません。** 期待される集合に含まれないツールに手を伸ばしたときにのみ失敗します。

だからこそ、これが過剰計画の検出器になります。期待される集合を仕事の範囲に絞ってください。

```
Expected: [suggest_dining]                                    ("where should I eat lunch?")
Actual:   [query_sites, plan_route, suggest_dining]

  subset:    FAIL ✗  (unexpected tool calls: query_sites, plan_route)
```

エージェントは質問に答えましたが、そこに至るまでに旅程全体を計画しました。より難しい依頼では、このパターンは混乱と相関し、すべてのリクエストでトークンとレイテンシのコストがかかります。

## ケースごとに 2 つのスコア

次のページで使うランナーは、Luminara のコア 6 ケースを実行します。

```bash
cd /workshop/edd-workshop/travel-agent
npm run eval
```

各ケースには 2 つのスコアが付き、両方の列を持つテーブルとして表示されます。

1. **トラジェクトリスコア** (0 または 1): エージェントは期待されるツールを期待されるモードで呼んだか。
2. **コンテンツスコア** (0.0-1.0): LLM ジャッジは、ケースのルーブリックに対して回答を満足できるものと判断したか。

(モジュール 4 では独自のケースを持つ `time_estimator` ツールを追加します。それらが存在すると、`-- --all` がそれらも実行します。)

:::alert{type="info" header="仕組み: travel-agent/eval/ の中身"}
```
travel-agent/eval/
├── cases.ts                 # 6 test cases with expected_trajectory
├── trajectory.ts            # tool-call sequence matcher (4 modes)
├── judge.ts                 # Claude-as-judge content evaluator
└── run-experiment.ts        # CLI runner
```

`cases.ts` のすべてのケースは、このインターフェースに正確に一致します。

```typescript
type TrajectoryMatchMode = "superset" | "in_order" | "exact" | "subset";

interface Case {
  name: string;
  prompt: string;                    // the user message
  expected_trajectory: string[];     // expected tool-call names
  trajectory_match: TrajectoryMatchMode;
  rubric: string;                    // what the LLM-judge checks in the answer
  must_contain?: string[];           // optional substring assertions
  must_not_contain?: string[];       // optional (e.g. closure-day violations)
}
```
:::

## コンテンツのレンズだけでは不十分な理由

Online Eval はセッションの入力と出力しか見ないため、「この回答は有用だったか」には答えられますが、「どのツールが実行されたか」には決して答えられません。次の例を考えてください。

- エージェントに、Grand Museum を含む 3 日間の旅行について尋ねます。
- モデルの差し替えにより、`query_sites` を省いて営業時間をハルシネーションします。
- ハルシネーションした営業時間が、学習データから記憶していたもので偶然正しかったとします。
- Online Eval はそのセッションを 0.9 と採点します。有用で正確だと。

トラジェクトリのレンズは、同じセッションを失敗とします。`query_sites` が期待されていたのに、一度も呼ばれなかったからです。エージェントは運が良かったのです。次回はそうはいかず、捉えられたリグレッションではなく本番インシデントが手に入ります。

:::alert{type="success" header="なるほどポイント: 素晴らしい回答が誤った経路から生まれることがある"}
運良く当たった回答を捉えられるのはトラジェクトリのレンズだけです。正しい経路なのにまとめの文章が下手なケースを捉えられるのはコンテンツのレンズだけです。

レンズが一致すれば判断は明白になります。レンズが食い違えば、調査に値する何かを見つけたということです。モジュール 3 の実験は、まさにそうした食い違いを生み出すように作られています。
:::

## ステップ 1: ベースラインの 6 ケースにざっと目を通す

Code Editor の **Explorer** で `travel-agent/eval/cases.ts` を開きます。

6 つのケースがモードにどう分散しているかに注目してください。**`superset` が 4 つ** (網羅性、順序は無関係)、**`in_order` が 1 つ** (`luminara_3day_balanced`、sites が route に先行しなければならない)、**`subset` が 1 つ** (`luminara_dining_only_scoped`、「Skyline Tower にもういるので、近くでランチはどこがいい」、過剰計画の検出器) です。

**`exact` を使っているものはなく、それが実務的な教訓です。** 1 回のリトライや `query_sites` の 1 回の追加呼び出しで失敗するため、`exact` は自分でツール呼び出しを決める LLM ではなく決定的なパイプラインに属します。形の多様性にも注目してください。単一ツールの検索 (`luminara_weekend_attractions`)、3 ツールの完全な計画 (`luminara_2day_history_monday`)、予算制約のある複数日の依頼 (`luminara_3day_balanced`) です。

次は、エージェントを変更し、これらのケースが Online Eval が見落とすリグレッションを捉える様子、そしてその逆を観察します。
