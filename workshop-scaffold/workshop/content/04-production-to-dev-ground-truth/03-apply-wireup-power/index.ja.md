---
title: "4.3 配線の Power を適用する"
weight: 30
---

新しい専門ツールがバックログにあります。**`query_events`** で、Coordinator がこれを呼んで Luminara のイベント (コンサート、フェスティバル、パレード) を日付で調べます。Coordinator と AgentCore Observability に配線し、その呼び出しが `query_sites`、`plan_route`、`suggest_dining` と並んでネストしたスパンとして現れるようにする必要があります。

やり方はモジュール 1 でもうご存じです。ここでの問いはこうです。適切な Power があれば、コーディングエージェントはこれをできるでしょうか。

## ステップ 1: Power を読む

Code Editor の **Explorer** で `kiro-powers/byo-agentcore-evaluation/POWER.md` を開きます。数百行あるので、ターミナルではなくエディターで読んでください。

これは BYO 配線パターンの正式な記述です。OTEL の `service.name` リソース属性、OpenInference のスパン種別 (AGENT / LLM / TOOL)、オンライン評価の設定、そして新しい専門ツールを登録して計測する方法です。モジュール 1 の Path B と同じ内容を、コーディングエージェント向けにパッケージしたものです。

:::alert{type="info" header="仕組み: この Power は登録済みの Claude Code skill でもあります"}
`byo-agentcore-evaluation` という名前のネイティブ **skill** として事前登録されており (`travel-agent/.claude/skills/` 経由で、正式な POWER.md を指しています)、Kiro では同じファイルが Power としてネイティブに読み込まれます。1 つのファイル、3 つの利用形態です。パス参照 (汎用)、Claude Code skill、Kiro Power です。

下のプロンプトは *どの* コーディングエージェントでも動くよう、Power をファイルパスで参照しています。Claude Code なら、タスクを説明するだけで自分で見つけます。
:::

:::alert{type="warning" header="Explorer でファイルが見つからない場合"}
Explorer のルートが `/workshop/edd-workshop` になっているか確認してください。Code Editor がリポジトリを事前展開する場所であり、シェルが開始する場所です。ターミナルで `ls /workshop/edd-workshop` を実行すれば、リポジトリがそこにあることを確認できます。
:::

## ステップ 2: 専門ツールの出発点となるスケルトンを生成する

スキーマ、ファクトリー関数、`execute` の形は `src/agents/sites-agent.ts` を写したものです。

:::code{language=bash showCopyAction=true showLineNumbers=false}
cd /workshop/edd-workshop/travel-agent
mkdir -p src/agents
cat > src/agents/events-agent.ts <<'TS'
import { Type, type Static } from "@sinclair/typebox";
import type { AgentTool, AgentToolResult } from "@mariozechner/pi-agent-core";

const EventsQuerySchema = Type.Object({
  date: Type.String({
    description: "Date to look up events (e.g., 'Friday' or '2026-06-12')",
  }),
});

type EventsQuery = Static<typeof EventsQuerySchema>;

export function createEventsAgentTool(): AgentTool<typeof EventsQuerySchema, unknown[]> {
  return {
    name: "query_events",
    label: "Query Events",
    description:
      "Look up Luminara events (concerts, festivals, parades) for a given date. Returns event name, time, venue, and ticket info.",
    parameters: EventsQuerySchema,
    execute: async (toolCallId, args, signal, onUpdate) => {
      // TODO: load mock events from src/data/events.ts and filter by date.
      return {
        content: [{ type: "text", text: "TODO: not implemented" }],
        details: [],
      } satisfies AgentToolResult<unknown[]>;
    },
  };
}
TS
:::

このスケルトンは **意図的に未完成** で、Power が 1 回のパスで埋めるべき 4 つの欠落があります。

- `src/coordinator.ts` への登録がありません。`tools: [...]` 配列に `createEventsAgentTool()` が含まれていないため、Coordinator はこれを呼び出せません。
- `src/data/events.ts` にモックデータがありません。`execute` のラムダはフィルターする対象を持ちません。
- `test/unit/events-agent.test.ts` にテストがありません。ツールを単体で検証する方法がありません。
- Coordinator のシステムプロンプトの「Your Capabilities」に `query_events` の記載がありません。

## ステップ 3: コーディングエージェントに Power を適用させる

Code Editor で `src/agents/events-agent.ts` を開きます。Claude Code を起動します (**Terminal → New Terminal** のあと `claude`、またはサイドバーのパネルを使用)。

:::alert{type="info" header="初回起動で見えるもの、そして見込むべき承認"}
Code Editor の Claude Code は **Amazon Bedrock 経由で** すでに認証済みなので、設定する API キーはありません。バナーには `Sonnet 4.6 · Amazon Bedrock` と表示されます。

次の 2 つは想定どおりで、どちらも問題ではありません。

- 隅に出る `✗ Auto-update failed: no write permission to npm prefix`。`claude` はシステム全体にインストールされており、ご自身のユーザーはそこに書き込めません。無視してください。
- Claude Code は **manual モード** で始まるので、各アクションの前に権限を求めて止まります。このタスクではおおよそ **8 回の承認** が必要です (Power の読み取り、3 ファイルの書き込み、coordinator の 2 か所の編集、`mkdir` 1 回、それから `vitest` と `tsc`)。*「Yes, allow all edits during this session」* と答えても残りは静かになりません。ファイルの作成、編集、コマンドの実行はそれぞれ別の権限です。

  最初に **shift+tab** を押すと `accept edits on` に切り替わり、ファイル編集のプロンプトが消えます。ただしすべてが消えるわけではありません。`kiro-powers/` はプロジェクトディレクトリの外にあるため `POWER.md` の読み取りは引き続き尋ねますし、シェルコマンドは毎回尋ねます。そのモードでも 2 〜 3 回のプロンプトを見込んでください。

止まって見えるときは、ほぼ必ずプロンプトを待っています。
:::

このプロンプトを渡してください。

> Apply the `byo-agentcore-evaluation` Power at `/workshop/edd-workshop/kiro-powers/byo-agentcore-evaluation/POWER.md` to `src/agents/events-agent.ts`.
> The new tool should follow the same pattern as `src/agents/sites-agent.ts`. Specifically:
>
> 1. Implement `execute` to load mock events from `src/data/events.ts` (create that file with at least 5 events covering different days) and filter by the requested date.
> 2. Register the tool in `src/coordinator.ts` by adding `createEventsAgentTool()` to the `tools` array and updating the system prompt's "Your Capabilities" section to list `query_events`.
> 3. Add a unit test at `test/unit/events-agent.test.ts` that verifies the tool returns events for a known date and an empty result for a date with no events.
> 4. Print a summary of the changes made. Do not verify spans or query AWS: a later step covers that.

4 つの成果物 (スケルトン、モックデータ、coordinator の編集、テスト) を生み出し、それぞれがコンパイルできることを確認するはずです。

エージェントの動きについて知っておくとよいことが 2 つあります。

- おそらく **5 つ目の** ファイル `src/data/types.ts` にも手を入れ、既存のものと並ぶイベント型を追加します。それは正しい判断で、ステップ 4 の確認はそれを探しません。
- プロンプトの最後の行が重要です。Power は可観測性と評価の配線を端から端までカバーしているので、その行がないとエージェントは AWS に進んでスパンを探し回りがちです。そして何も見つけられません。いま書いたコードは計測済みのエントリポイントをまだ通っていないからで、それこそがステップ 5 とステップ 6 の役目です。

  その行は迷走を減らしますが、なくすわけではなく、どれだけ目に見えるかは実行によります。実測したある実行では、この行があっても最後に 1 回 `aws/spans` に対して `aws logs filter-log-events` に手を伸ばしました。別の実行はきれいに終わり、AWS の呼び出しをまったくせずサマリーで止まりました。どちらも正常です。プロンプトが出た場合は **No** と答え、止まってサマリーを出力するよう伝えてください。失うものはありません。ステップ 5 が見つけるべきスパンを生んだ後で、ステップ 6 が同じクエリを後から実行します。プロンプトがまったく出なければ、問題はありません。

## ステップ 4: 4 つの成果物がすべて存在することを確認する

:::code{language=bash showCopyAction=true showLineNumbers=false}
ls -la src/agents/events-agent.ts \
       src/data/events.ts \
       test/unit/events-agent.test.ts && \
  grep -q 'createEventsAgentTool' src/coordinator.ts && \
  echo "All 4 artifacts present and Coordinator is wired."
:::

期待される結果: 新しい 3 ファイル (それぞれ数百バイトから数 KB) の `ls` 一覧のあとに `All 4 artifacts present and Coordinator is wired.` が表示されます。

:::alert{type="warning" header="ls が No such file or directory で途中終了する場合"}
コーディングエージェントがファイルを 1 つ飛ばしています。多くはモックデータかユニットテストです。ファイルがないというメッセージをチャットに貼り戻し、そのファイルを作るよう頼み、確認を再実行してください。
:::

## ステップ 5: 配線を確認する

ツールを単体でスモークテストします。

:::code{language=bash showCopyAction=true showLineNumbers=false}
npx tsx -e "import { createEventsAgentTool } from './src/agents/events-agent.ts'; const t = createEventsAgentTool(); console.log(t.name, '|', t.description.slice(0, 60));"
:::

期待される出力: ツールの **名前** が `query_events` で、そのあとにコーディングエージェントが決めた説明が続きます。名前はスケルトンで固定ですが説明はそうではないので、`query_events | Query city events happening on a specific date in Luminara` はスケルトンの元の文言と同じくらい正しい結果です。

コーディングエージェントが書いたユニットテストを実行します。

:::code{language=bash showCopyAction=true showLineNumbers=false}
npm test -- events-agent
:::

期待される結果: vitest が `events-agent` のテストファイルの合格を報告します。ケースをいくつ書くかはコーディングエージェントが決めるので、**少なくとも 2 つ** (肯定的なものと空の結果) を見込んでください。それより多くてもかまいませんし、多いほうが良いことも多いです。

次に、`query_events` を起動させるはずのクエリで Coordinator にプロンプトを与えます。`src/main.ts` ではなく **Path B のアダプター経由で** 実行してください。スパンをエクスポートするのはアダプターで、ステップ 6 がそれを確認します。

まずコーディングエージェントが書いたファイルから日付を 1 つ取ってください。モックの日付はエージェントが作ったものであり、曜日名を使ったのかカレンダー日付を使ったのかは前もって分からないからです。

:::code{language=bash showCopyAction=true showLineNumbers=false}
grep -m1 -A1 'date:' src/data/events.ts
:::

それからその日付について尋ねます。

:::code{language=bash showCopyAction=true showLineNumbers=false}
cd /workshop/edd-workshop/openinference-aws-adapter
USER_QUERY="Are there any events in Luminara on 2025-08-04?" npm start   # use YOUR date
:::

期待される結果: 応答が少なくとも 1 件のイベントを時刻と会場とともに列挙し、実行が `[run] Flushing spans...` で終わります。

:::alert{type="info" header="「イベントは見つかりませんでした」という回答も合格です"}
代わりに「this Friday」のような相対表現で尋ねると、エージェントは今日の日付を基準に解決するので、作られたモックデータにほぼ一致しません。実測では、2025-08-04 から 2025-08-09 しかカバーしていないデータに対して `{"date":"2025-07-25"}` でツールを呼び、「現在掲載されているイベントはありません」と答えました。これは尋ねられた質問に対する **正しい** 回答です。ツールは実行されたのでステップ 6 のスパンは現れますし、実際にどの日付を尋ねたかはスパンの `input.value` で確認できます。
:::

:::alert{type="info" header="仕組み: ここで `npx tsx src/main.ts` を使わない理由"}
`src/main.ts` は Coordinator を直接、計測なしで実行します。モジュール 0 とまったく同じです。正しく回答しますが何も出力しないので、ステップ 6 はスパンを見つけられず、このステップの意義が失われます。アダプターは同じ Coordinator をインポートしてラップします。だから新しいツールは、アダプターに触らずに可観測になります。

**Path A を選びましたか。ここでは `agentcore deploy` では解決できません。そしてこれは理解する価値があります。** ご自身の Runtime が動かしているのは `travel-agent-strands/` で、独自の 3 ツールを持つ別の Python コードベースです。いま追加した `query_events` は **TypeScript** のエージェントにあるので、デプロイされた成果物には入っておらず、再デプロイしてもそこに入れることはできません。実際の Runtime での実測では、`agentcore invoke "Are there any events in Luminara this Friday?"` は `query_sites` からの観光地一覧で答え、`query_events` をまったく呼びませんでした。

いま拡張したのと同じ TypeScript の Coordinator をラップするリファレンスアダプターを使ってください。

```bash
cd /workshop/edd-workshop/solutions/module-1/openinference-aws-adapter
npm install                       # about 10 seconds, one time
source /workshop/edd-workshop/config.env
USER_QUERY="Are there any events in Luminara on <a date from src/data/events.ts>?" npm start
```

これはご自身の Runtime のサービス名ではなく `service.name: travel-agent-edd-workshop` の下に出力しますが、ここでは問題ありません。ステップ 6 はサービスではなく **スパン名** でフィルターします。
:::

:::alert{type="warning" header="vitest が No test files found, exiting with code 1 と言う場合"}
コーディングエージェントが `test/unit/events-agent.test.ts` を書いていません。これを貼り戻してください。

> The unit test at `test/unit/events-agent.test.ts` was not created. Please create it now, using vitest and following the same style as the existing `test/eval/trajectory.test.ts`. The test should verify that the tool returns events for a known date in the mock data, and an empty result for a date with no events.

それから `npm test -- events-agent` を再実行し、ケースが合格することを確認してから続けてください。
:::

## ステップ 6: 新しいツールが可観測であることを証明する

ユニットテストの合格は、ツールが動くことしか証明しません。Power の本当の約束はこうです。新しいツールが、アダプターの変更ゼロで **可観測性と評価のパイプライン** に乗ることです。上のアダプター実行は `execute_tool query_events` スパンを出しているはずです。

:::code{language=bash showCopyAction=true showLineNumbers=false}
aws logs filter-log-events \
  --log-group-name aws/spans \
  --filter-pattern '"execute_tool query_events"' \
  --start-time $(($(date +%s) * 1000 - 600000)) \
  --max-items 3 --region us-east-1 \
  --query 'events[0].message' --output text | head -30
:::

期待される結果: `execute_tool query_events` という名前のスパンが、`openinference.instrumentation.pi-mono` スコープの下にあり、`openinference.span.kind: TOOL` を持ち、日付の引数を載せた `input.value` と、返されたイベントを載せた `output.value` を持ちます。実際の実行からの抜粋です。

```json
{"name":"execute_tool query_events","kind":"INTERNAL",
 "scope":{"name":"openinference.instrumentation.pi-mono"},
 "attributes":{"gen_ai.tool.name":"query_events",
   "input.value":"{\"date\":\"Friday\"}",
   "output.value":"...Luminara Jazz Night (concert) ... Harbor Fireworks Display (festival)...",
   "openinference.span.kind":"TOOL","tool.name":"query_events",
   "session.id":"16cd673b-8781-4f15-aacd-93448ecb834a"}}
```

JSON のあとに `None` の行が続くのは正常です。`--max-items` はページネーションするため、一致の次のページでは `events[0].message` が空になります。

:::alert{type="warning" header="スパンのクエリが空で返る場合"}
OTLP のエクスポートに約 10 秒与えて再実行してください。それでも空の場合は、ステップ 5 の呼び出しが実際に `query_events` を呼んだか確認してください。ツール呼び出しなしで記憶から答えた応答は、それ自体が捉える価値のあるトラジェクトリのバグです。
:::

:::alert{type="success" header="いま起きたこと: 因果の連鎖"}
1. **あなたの行動**: コーディングエージェントが新しいツールを 1 つ登録しました。アダプター、CFN、評価設定には誰も触っていません。
2. **機構**: モジュール 1 のアダプターはツール実行のライフサイクルイベントを *汎用的に* フックするので、登録されたどのツールの呼び出しも、評価器がすでに見ているのと同じ `openinference.instrumentation.pi-mono` スコープの下で `TOOL` スパンになります。
3. **証拠**: いま `aws/spans` から引き出した `execute_tool query_events` スパンで、1 分前に実行した呼び出しのタイムスタンプが付いています。
4. **ルール**: 正しく行った配線は *繰り返すのではなく継承される* ものです。エージェントのライフサイクルを 1 回計測すれば、将来のすべてのツールは構造上、可観測で評価可能になります。

**反証チェック:** アダプターがツールごとにスパンの出力をハードコードしていたら (`if (tool === "query_sites") ...`)、この確認は `query_events` について何を示し、誰が直さなければならなかったでしょうか。(何も示さず、毎回人間が直すことになります。それが Power が防ぐために存在するアンチパターンです。)
:::

## 証明したこと

配線の全体、つまりスケルトンから Coordinator への登録、ユニットテスト、そして **検証された可観測性** まで、適切なコンテキストを与えればコーディングエージェントに任せられるほど機械的です。4 つ目、5 つ目、20 個目の専門ツールが評価パイプラインに到達するのに、もう人間の時間はかかりません。

**次へ: [本番データをテストケースに変換する](../04-transform-to-test-cases/)**。そこでは 2 つ目の Power (EDD 駆動開発のループ) が、まったく新しいツールをテストファーストで作ります。
