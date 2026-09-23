---
title: "4.2 本番のトラジェクトリを引き出す"
weight: 20
---

ステップ 1 から 5 では、データの流れが見えるようスクリプトで低スコアの本番セッションを抽出します。ステップ 6 では同じ仕事をコーディングエージェントに任せます。どちらも `eval/cases.ts` に新しいケースが加わって終わります。

## ステップ 1: 評価結果のロググループを見つける

ロググループを一覧するのではなく、**稼働中の** Online Evaluation Config から解決します。

:::code{language=bash showCopyAction=true showLineNumbers=false}
cd /workshop/edd-workshop/travel-agent

# Which config is actually running right now
EVAL_CFG_ID=$(aws bedrock-agentcore-control list-online-evaluation-configs \
  --region us-east-1 \
  --query 'onlineEvaluationConfigs[0].onlineEvaluationConfigId' --output text)

# ...and where that config writes its scores
EVAL_LG=$(aws bedrock-agentcore-control get-online-evaluation-config \
  --region us-east-1 --online-evaluation-config-id "$EVAL_CFG_ID" \
  --query 'outputConfig.cloudWatchConfig.logGroupName' --output text)

echo "Evaluation log group: $EVAL_LG"

if [ -z "$EVAL_LG" ] || [ "$EVAL_LG" = "None" ]; then
  echo "No evaluation config found. Deploy Module 2 first, then generate traffic:"
  echo "  cd /workshop/edd-workshop/travel-agent-strands && agentcore invoke \"...\"   # Path A"
  echo "  cd /workshop/edd-workshop/openinference-aws-adapter && USER_QUERY=\"...\" npm start   # Path B"
fi
:::

:::alert{type="warning" header="最初の `/evaluations/` ロググループをそのまま取ってはいけない理由"}
たいていそれが誤ったロググループだからです。Online Evaluation Config が再生成されるたびに (任意のページ 2.6 がまさにそれを行います) AgentCore は **新しい** 結果ロググループを作り、古いものはそのまま残します。そして `logGroups[0]` は最も古いものを返します。2.6 のあとの実アカウントでの実測です。

```
logGroups[0]  ..._DEFA-AhhqS6Ez4L    3 events, no trajectory scores   <- what the prefix scan picks
live config   ..._DEFA-h8MFHfGuoF   15 events, TrajectoryCompliance   <- what you want
```

古いグループを掘るのは静かな行き止まりです。以下のトリアージは修正すべきものを何も報告せず、どれだけ待っても新しいセッションはそこに現れません。稼働中のグループに書かれているからです。手で確認したい場合は、`./scripts/read-eval-scores.sh` が同じやり方で解決します。
:::

## ステップ 2: 評価結果を抽出する

:::code{language=bash showCopyAction=true showLineNumbers=false}
# Extract evaluation results
# --output json | jq -r '.[]' gives ONE record per line. Do not use --output text
# here: it joins records with TABs, so the file becomes a single line and the
# line-based parser below silently reads nothing.
aws logs filter-log-events \
  --log-group-name "$EVAL_LG" \
  --filter-pattern '"gen_ai.evaluation.score.value"' \
  --max-items 20 \
  --query 'events[*].message' \
  --output json | jq -r '.[]' > /tmp/eval-results.jsonl

echo "records: $(wc -l < /tmp/eval-results.jsonl)"

# Preview what we got
head -3 /tmp/eval-results.jsonl | jq .
:::

各ログイベントには次が含まれます。
- `gen_ai.evaluation.score.value`: スコア。その評価器が使う任意のスケールで
- `gen_ai.evaluation.name`: このスコアを生成した評価器が **どれか** (実レコードで実測されたキー。より古いレコードを扱う必要があるコードは `gen_ai.evaluation.evaluator_id` にフォールバックします)
- `gen_ai.evaluation.explanation`: ジャッジ (またはコードベースの検査) がそう採点した理由
- セッションの入力 (ユーザーのクエリ) と出力 (エージェントの応答)
- セッション ID (X-Ray のトラジェクトリデータと突き合わせるため)

**期待される結果: 掘り出そうとしている本番データです。** コンテンツスコア (ここでは 4.0/5.0) が高いところにある一方、`TrajectoryCompliance` の `FAIL` (0.0、"missing query_sites, plan_route; actual suggest_dining") がテストケースに変える価値のあるセッションを示します。それらの `FAIL` がグラウンドトゥルースの候補です。

![期待される結果: このトリアージが掘り出す本番の評価レコード。TrajectoryCompliance の FAIL (0.0、query_sites/plan_route が欠落)、PASS (1.0)、そして高いコンテンツスコア (4.0/5.0) が並んで表示されている](/static/images/module-4/production-eval-source-data.png)

:::alert{type="success" header="2 つの評価器、2 つのスケール: 別々にトリアージしてください"}
ステップ 3.4 を実施した場合、すべてのセッションはコンテンツスコア (`Builtin.Helpfulness` 0.0-1.0、またはご自身のカスタムルーブリック 1-5) と `TrajectoryCompliance` (0.0/1.0、PASS/FAIL) の **両方** を持ちます。混ぜた「ワースト 10」はすべての順位を誤ります。トラジェクトリの `0.0` とコンテンツの `0.45` は比較できません。

`evaluator_id` でグループ化し、それぞれの尺度でトリアージしてください。
- **コンテンツ評価器**: 昇順に並べ、最低スコアのものとエラーを取る。
- **`TrajectoryCompliance`**: すべての `FAIL` (スコア `0.0`) に注意が必要。並べるための勾配はありません。

両方を確認してください。健全なエージェントはもっともらしい回答を書くので、コンテンツスコアは高いところに集まり、掘り出す価値のあるセッションはトラジェクトリの `FAIL` に隠れます。
:::

:::alert{type="warning" header="トリアージが注意の必要なセッションを 0 件と報告する場合"}
**まず上の抽出が出力したレコード数を確認してください。** 複数のセッションが採点されたと分かっているのに `records: 1` と表示される場合、そのファイルは 1 行 1 JSON になっておらず、パーサーは何も読んでいません。`--output text` ではなく `--output json | jq -r '.[]'` を使い、書かれているとおりに抽出を再実行してください。

件数が正しく見えてもトリアージが 0 を報告する場合、それは失敗ではなく実際の結果です。新しいアカウントでは、エージェントはクリーンなモックデータに対して Sonnet 4.6 を動かすので、セッションは 1.0 近くのスコアになり、掘り出すものがほとんどありません。**続けるには悪いセッションが 1 つ必要** なので、モジュール 3.4 のステップ 6 と同じ手口で意図的に作り出しましょう。

```bash
cd /workshop/edd-workshop/openinference-aws-adapter
MODEL_ID=amazon.nova-lite-v1:0 \
  USER_QUERY="Plan a 2-day Luminara trip focused on history, arriving Monday." npm start
```

制約の多いクエリに対して弱いモデルを使うと `query_sites` を飛ばしがちで、それがまさに掘り出す価値のあるトラジェクトリ違反です。スコアのために 15 〜 25 分待ち、上の抽出を再実行してください。

注目すべき点: **悪いセッションを作るのに手間がかかりました。** それが本番でもこの問題の正直な姿です。低スコアのセッションはまれであり、だからこそ飽きることのない自動評価器がそれを見つける存在になります。
:::

:::alert{type="warning" header="filter-log-events がイベント 0 件を返す場合"}
`--limit` ではなく `--max-items` を使ってください。これらのロググループに対しては、生の `--limit` API パラメーターが、実際のスコアが存在しても黙って 0 件を返すことがあります。`--max-items` (AWS CLI 自身のクライアント側ページネーション上限) は実データを確実に返します。
:::

これは **実際の本番ユーザー入力** です。クエリのテキストとジャッジの説明は信頼できないものとして扱い、とくにコーディングエージェントに渡すときは注意してください。また、ステップ 5 がバージョン管理されたテストファイルにコミットする前に、PII (氏名、連絡先、住所) を除去してください。

## ステップ 3: 評価器ごとにフィルターしてパターンを抽出する

評価のフィールドはトップレベルではなく、ネストした `attributes` オブジェクトの下にあります。まずご自身のアカウントで `head -1 /tmp/eval-results.jsonl | jq .attributes` として 1 件を調べ、それから実行してください。

:::code{language=bash showCopyAction=true showLineNumbers=false}
# Parse out lowest-scoring sessions and evaluation errors, grouped by evaluator
cat /tmp/eval-results.jsonl | python3.12 -c "
import json, sys
from collections import defaultdict

by_evaluator = defaultdict(list)
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        record = json.loads(line)
        attrs = record.get('attributes', {})
        score = attrs.get('gen_ai.evaluation.score.value')
        error = record.get('error')
        evaluator = attrs.get('gen_ai.evaluation.name', 'unknown')

        if score is not None or error:
            by_evaluator[evaluator].append({
                'score': float(score) if score is not None else None,
                'error': error,
                'label': attrs.get('gen_ai.evaluation.score.label', 'N/A'),
                'explanation': attrs.get('gen_ai.evaluation.explanation', 'N/A'),
                'session_id': attrs.get('session.id', 'unknown'),
                'trace_id': record.get('traceId', '')
            })
    except (json.JSONDecodeError, TypeError) as e:
        # Do not swallow this. A parse failure here used to look like
        # 'no sessions need attention', which is indistinguishable from a
        # healthy agent.
        print(f'WARNING: could not parse a record ({e}). If you see this for every '
              f'record, /tmp/eval-results.jsonl is not one-JSON-per-line.',
              file=sys.stderr)
        continue

needs_attention = []
for evaluator, sessions in by_evaluator.items():
    is_pass_fail = all(s['score'] in (0.0, 1.0, None) for s in sessions) and 'trajectory' in evaluator.lower()
    if is_pass_fail:
        # PASS/FAIL evaluators (e.g. TrajectoryCompliance): every FAIL is needs-attention,
        # there's no gradient to sort by.
        flagged = [s for s in sessions if s['score'] == 0.0 or s['error']]
    else:
        # Graded content evaluators: sort ascending, take the lowest-scoring + errors.
        sessions.sort(key=lambda x: x['score'] if x['score'] is not None else -1)
        # Normalize the 'low' cutoff to the observed scale (1-5 vs 0.0-1.0)
        max_score = max((s['score'] for s in sessions if s['score'] is not None), default=1.0)
        cutoff = max_score * 0.8
        flagged = [s for s in sessions if s['score'] is None or s['score'] < cutoff][:10]
    for s in flagged:
        s['evaluator'] = evaluator
        needs_attention.append(s)

for s in needs_attention:
    print(json.dumps(s))
" > /tmp/low-scoring-sessions.jsonl

echo "Sessions needing attention (across all evaluators): $(wc -l < /tmp/low-scoring-sessions.jsonl)"
cat /tmp/low-scoring-sessions.jsonl | jq -r '"[\(.evaluator)] score=\(.score) session=\(.session_id)"'
:::

:::alert{type="info" header="任意: 実アカウントではこう見えました"}
両方の評価器をデプロイしてドッグフーディングした結果です。コンテンツスコア (`edd_workshop_travel_quality`) はすべてのセッションで 5 点満点の 4.0-5.0 に集まり、そこにトリアージすべきものはありませんでした。本当のシグナルは `0.0`/`FAIL` となった 2 つの `TrajectoryCompliance` セッションで、いずれも `query_sites`/`plan_route` が欠けていました。コンテンツスコアがまったく示唆しなかった、本物の違反です。
:::

## ステップ 4: フラグの付いた各セッションの元のクエリを解決する

評価のログイベントは `trace_id` だけを持ち、ユーザーのプロンプトは持ちません。プロンプトのテキストがどこにあるかは選んだパス次第なので、以下のリゾルバーは両方を試します。

| | Path B (OpenInference アダプター) | Path A (Runtime 上の Strands) |
|---|---|---|
| プロンプトのテキストの場所 | `aws/spans` にある **ルート** スパンの `input.value`。`openinference.span.kind: AGENT` を持つスパン | `/aws/bedrock-agentcore/runtimes/$RUNTIME_LOG_SUFFIX` にあるエージェントログレコードの `body.input.messages[]` |
| 理由 | OpenInference は I/O をスパンに載せる | Strands のスパンは `gen_ai.usage.*` と `gen_ai.request.model` を持つが **プロンプトのテキストは持たない**。入力と出力があるのはレコードのほう (モジュール 1 のチェック 2 が検証しているものです) |

Path B では、`input.value` の存在だけでなくスパンの種類で照合します。`TOOL` スパンも `input.value` を持ち、そこにはツールの引数が入っていて、ルートスパンより先にロググループに届きます。ルートスパンは実行が終わるまで閉じないからです。見つかった最初の `input.value` を取ると、ユーザーが尋ねた質問ではなく `{"attraction_name":"Royal Palace","meal_type":"dinner"}` のようなプロンプトがすべてのケースに入ってしまいます。

Path A ではメッセージの内容がメッセージの中にネストされた JSON 文字列なので、`json.loads` が 1 回追加で必要です。それを下の `_text_from_message` が扱います。

:::code{language=bash showCopyAction=true showLineNumbers=false}
source /workshop/edd-workshop/config.env

python3.12 -c "
import json, os, subprocess

AGENT_LG = '/aws/bedrock-agentcore/runtimes/' + (
    os.environ.get('RUNTIME_LOG_SUFFIX') or os.environ.get('SERVICE_NAME', ''))


def events(log_group, trace_id):
    '''Every record mentioning this trace id, in one API call.'''
    out = subprocess.run(
        ['aws', 'logs', 'filter-log-events',
         '--log-group-name', log_group,
         '--filter-pattern', f'\"{trace_id}\"',
         '--max-items', '20', '--region', 'us-east-1',
         '--query', 'events[].message', '--output', 'json'],
        capture_output=True, text=True).stdout
    try:
        return [json.loads(m) for m in (json.loads(out) or [])]
    except Exception:
        return []


def _text_from_message(msg):
    '''Strands nests the text as a JSON string inside content.content.'''
    content = msg.get('content')
    inner = content.get('content') if isinstance(content, dict) else content
    if isinstance(inner, str):
        try:
            parts = json.loads(inner)
        except Exception:
            return inner
        if isinstance(parts, list):
            for p in parts:
                if isinstance(p, dict) and p.get('text'):
                    return p['text']
    return None


def resolve_query(trace_id):
    # Path B: the prompt is on the ROOT span, the one whose span kind is AGENT.
    # Match on the kind, do not just take the first input.value in the trace:
    # TOOL spans carry an input.value too (their arguments), and they are
    # exported before the root span, which only closes at the end of the run.
    for span in events('aws/spans', trace_id):
        attrs = span.get('attributes', {})
        if attrs.get('openinference.span.kind') == 'AGENT' and attrs.get('input.value'):
            return attrs['input.value']
    # Path A: Strands puts it in the agent log record instead.
    for rec in events(AGENT_LG, trace_id):
        body = rec.get('body')
        if not isinstance(body, dict) or not isinstance(body.get('input'), dict):
            continue
        for msg in body['input'].get('messages', []):
            if msg.get('role') == 'user':
                text = _text_from_message(msg)
                if text:
                    return text
    return 'N/A'


with open('/tmp/low-scoring-sessions.jsonl') as f:
    sessions = [json.loads(line) for line in f if line.strip()]

for s in sessions:
    trace_id = s.get('trace_id', '')
    s['query'] = resolve_query(trace_id) if trace_id else 'N/A'

with open('/tmp/low-scoring-sessions-with-query.jsonl', 'w') as f:
    for s in sessions:
        f.write(json.dumps(s) + '\n')

print(f'Resolved queries for {len(sessions)} sessions')
for s in sessions:
    print(f\"  [{s['evaluator']}] score={s['score']} query={s['query'][:70]}\")
"
:::

フラグの付いたセッションごとに `filter-log-events` を 1 〜 2 回呼びます。下位 10-20 件には十分ですが、数百件向けには作られていません。

:::alert{type="warning" header="すべてのクエリが N/A で返る場合"}
Path A では `RUNTIME_LOG_SUFFIX` が設定されているか確認してください (`source config.env` の後に `echo $RUNTIME_LOG_SUFFIX`)。空だとリゾルバーは `/aws/bedrock-agentcore/runtimes/` を見に行き、何も見つけません。また、`aws/spans` に対する Logs Insights の `start-query` だけではこれを解決できないことにも注意してください。Path A ではプロンプトのテキストがそもそもスパンにないからです。
:::

## ステップ 5: Case オブジェクトに変換する

抽出したセッションを `Case` インターフェースに変換します。これはスクリプトをディスクに書き出し、次のコマンドがそれを実行します。

:::code{language=bash showCopyAction=true showLineNumbers=false}
mkdir -p scripts
cat > scripts/generate-cases-from-production.ts <<'TS'
import { readFileSync } from 'fs';
// Import the real interface instead of redeclaring it, so a field rename in
// cases.ts shows up here as a type error rather than as cases that merge
// cleanly and then run with an undefined prompt.
import type { Case } from '../eval/cases.js';

interface LowScoringSession {
  score: number;
  query: string;
  explanation: string;
  session_id: string;
  evaluator: string;
  error?: string;
}

const sessions: LowScoringSession[] = readFileSync('/tmp/low-scoring-sessions-with-query.jsonl', 'utf-8')
  .split('\n')
  .filter(Boolean)
  .map(line => JSON.parse(line));

// One session can be flagged by BOTH evaluators (a trajectory FAIL usually drags
// the content score down too), so group by session before generating cases.
// Without this you get two identical cases for one production failure.
const bySession = new Map<string, LowScoringSession[]>();
for (const s of sessions.filter(s => s.query && s.query !== 'N/A')) {
  const key = s.session_id || s.query;
  bySession.set(key, [...(bySession.get(key) ?? []), s]);
}

const newCases: Case[] = [...bySession.values()].map((flags, i) => ({
  name: `production_regression_${i + 1}`,
  prompt: flags[0].query,
  // Conservative: expect at least query_sites to be called
  expected_trajectory: ['query_sites', 'plan_route'],
  trajectory_match: 'in_order' as const,
  // Every evaluator that flagged this session, so the rubric carries both lenses
  rubric: flags
    .map(f => f.error
      ? `Fix the evaluation error: ${f.error}`
      : `[${f.evaluator}] ${f.explanation}`)
    .join(' | '),
}));

console.log('// Generated from production low-scoring sessions');
console.log('// Review and adjust expected_trajectory and rubric before committing');
console.log(JSON.stringify(newCases, null, 2));
TS
:::

実行します。

:::code{language=bash showCopyAction=true showLineNumbers=false}
npx tsx scripts/generate-cases-from-production.ts
:::

出力をレビューし、各ケースの `expected_trajectory` を実際に正しい経路に合わせて直してから `eval/cases.ts` にマージし、配線されたことを証明するため **新しいケースを実行** してください。

:::code{language=bash showCopyAction=true showLineNumbers=false}
npm run eval -- --case production_regression_1
:::

マージが明らかに問題なさそうに見えても実行してください。`eval/` は `tsconfig.json` の `include` の外にあり、`tsx` は型チェックなしでトランスパイルするため、フィールドが `Case` インターフェースに一致しないケースでも `npm run build` は失敗しません。プロンプトが undefined、ルーブリックが undefined の状態で走り、尋ねてもいない質問に対するスコアを報告します。

:::alert{type="warning" header="ジャッジの説明をテストケースに貼る前に読んでください"}
説明は証拠であって判定ではなく、ときにはエージェントについてではなく **評価** について語っています。この演習で実際に出たものです。

> "The user's original query isn't shown (only the agent response is provided as both
> query context and response) ... Without tool output to compare against, I cannot
> confirm factual accuracy."

そのコンテンツスコアは、部分的にはジャッジが見られたものについての話でした。ここからそのまま写した `rubric` は、評価器の死角をご自身のエージェントへの要件として符号化してしまいます。回答の実際の欠落を述べている部分は残し、ジャッジ自身のコンテキスト不足を述べている部分は落としてください。
:::

## ステップ 6: 同じ仕事をコーディングエージェントに任せる

上のすべては機械的で、それこそコーディングエージェントの用途です。このプロンプトを渡してください。

:::alert{type="info" header="ここが Claude Code の初運転です: 承認のプロンプトを見込んでください"}
これはワークショップで最初の委任タスクで、Claude Code は **manual モード** で始まります。各アクションの前に権限を求めて止まり、シェルコマンドはファイル編集とは別に毎回尋ねます。このタスクはほぼ AWS CLI の呼び出しなので、最初の 1 回の前に尋ね、探索の途中でも再び尋ねます。最初に **shift+tab** を押すと `accept edits on` に切り替わり、ファイル編集のプロンプトは静かになりますが、シェルのものは静かになりません。

止まって見えるときは、ほぼ必ずプロンプトを待っています。ページ 4.3 にこの注記のより詳しい版があり、初回起動のバナーと自動更新の警告の意味も説明しています。
:::

> Query the AgentCore evaluation results log group for the lowest-scoring sessions and any evaluation errors. In healthy agent systems, scores cluster high (0.8-1.0), so focus on the bottom 10 sessions by score and any sessions with LogEventMissingException or other errors. For each session needing attention, extract the user query, the tool-call trajectory, and the judge's explanation. Transform these into new test cases matching the `Case` interface in `eval/cases.ts`. Focus on patterns we don't already cover in the existing cases.
>
> The user's prompt text is not in the same place on both paths. On **Path B** it is on the root span in `aws/spans`, the one whose `openinference.span.kind` is `AGENT`, in `input.value`. On **Path A** the Strands spans carry **no prompt text at all**: it lives in the agent log record's `body.input.messages[]` in `/aws/bedrock-agentcore/runtimes/$RUNTIME_LOG_SUFFIX`, as a JSON string nested inside the message content. Check which path this account is on before you start digging.

:::alert{type="warning" header="プロンプトのテキストの場所を伝えないと、誤ったロググループを探し回ります"}
2 つ目の段落は任意の飾りではありません。これを付けずに Path A のアカウントで実測したところ、エージェントは `aws/spans` にユーザー入力を持つ `AGENT` スパンを探し、(Strands はプロンプトのテキストをスパンに置かないので、正しく) 何も見つけられず、それからスパンとランタイムのロググループの間を約 10 回の承認ラウンドにわたって行き来し、ケースを 1 つも書きませんでした。ステップ 4 の表が伝えているのと同じ事実であり、スクリプトの経路もまったく同じ理由でそれを必要とします。
:::

エージェントは次を行います。

1. AWS CLI を使って評価用ロググループに **問い合わせる**
2. 最低スコアのセッションと評価エラーを **フィルターする**
3. X-Ray のトレースと **突き合わせて** 実際のツール呼び出しトラジェクトリを抽出する
4. 既存のケースと **比較して** 重複を避ける
5. 適切な `expected_trajectory` と `rubric` を持つ新しい `Case` オブジェクトを **生成する**
6. そのケースを `eval/cases.ts` に直接 **書き込む**

あなたの仕事は、生成されたケースをレビューし、それぞれの `expected_trajectory` を検証することです。人間が判断を、エージェントが実行を担います。

スクリプトの経路はデータの流れを教えてくれますし、コーディングエージェントが使えない場所で使うべきものです。ただ、6 ステップのシェルパイプラインを毎週いつまでも回す人はいません。委任すれば、スケジュール (毎週、あるいはトラフィックが変わったあと) で走り、誰かが更新を思い出さなくてもグラウンドトゥルースは新鮮に保たれます。どちらにせよ規律は変わりません。拡張したケース集合で両方のレンズが緑にならない限り出荷しないことです。

**次へ: [配線の Power を適用する](../03-apply-wireup-power/)。**
