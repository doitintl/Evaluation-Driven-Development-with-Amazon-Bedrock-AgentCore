---
title: "Path B.4 実行と確認"
weight: 40
---

**シナリオ。** アダプターは書き終わり、インフラもデプロイ済みです。まだ何も記録されていません。テレメトリはパイプラインが稼働した後の呼び出ししか捕捉しないからです。このステップで最初の実際のトラジェクトリを生成し、アダプターがモジュール 2 に必要なものを出力していることを証明します。

## エージェントを呼び出す

まず、パイプラインがスパンを受け付けていることを確認します。受け付けていない場合、X-Ray はスパンを `400 Bad Request` で拒否し、それらは永久に失われます。

```bash
cd /workshop/edd-workshop
./scripts/verify-telemetry.sh
```

チェック 1 が `destination=CloudWatchLogs status=ACTIVE` と表示される必要があります。チェック 3 が「no spans」で失敗するのは、現時点では想定どおりです。まだエージェントを実行していません。

:::alert{type="warning" header="チェック 1 が ACTIVE と表示されない場合"}
B.2 のスタック完了から **6 〜 10 分** を見込んでください。通常は B.3 でアダプターを構築する時間がこの待ちを吸収します。早く到達した場合は、もう 1 分待って再実行してください。
:::

次にエージェントを実行します。

```bash
cd /workshop/edd-workshop/openinference-aws-adapter
npm start
```

期待される出力:
```
[run] Agent: travel-agent-edd-workshop
[run] Session: 085b56e0-f2f9-46f8-b188-c45d8f28a00a
[run] Region: us-east-1
[run] Scope: openinference.instrumentation.pi-mono
[run] Traces → xray.us-east-1.amazonaws.com
[run] Query: "Plan a 3-day trip to Luminara with cultural sites and local dining"

--- Agent Response ---

🌟 Your 3-Day Luminara Itinerary...

[run] Flushing spans...
[run] Done.
[run] - Traces + full trajectory: CloudWatch GenAI Observability
[run] - AgentCore Online Eval scores these spans directly (Module 2)
```

:::alert{type="info" header="➡️ あなたのフレームワークの場合"}
`npm start` (内部で `tsx src/run.ts` を実行) は **pi-mono / TypeScript** のエントリーポイントです。ご自身のフレームワークでは、その言語のツールチェーンで自前のエントリーポイントを実行します。以下の X-Ray と CloudWatch での確認はすべて、**どのフレームワークでも同一** です。エクスポートされた OpenInference のスパンを調べるもので、それを生成したコードを調べるものではないからです。
:::

## 確認: 自分のトラジェクトリを読む

まず、パイプラインが健全で、レコードがモジュール 2 の必要とする形状になっていることを確認します。

```bash
cd /workshop/edd-workshop
./scripts/verify-telemetry.sh
```

**チェック 1 と 3 が成功** し、チェック 2 がログレコードなしと報告されるはずです。それが正しい Path B の形状です。アダプターはスパンをエクスポートし、ログレコードは出力しないため、エージェントのロググループは空のままで、`aws/spans` のスパンが証拠になります。スクリプトはそれを失敗と呼ぶのではなく、明示的に説明します。

:::alert{type="warning" header="Path A も実施した場合はサービス名を明示してください"}
Path A の `capture-runtime-names.sh` は `RUNTIME_SERVICE_NAME` を `config.env` に書き込み、スクリプトは `SERVICE_NAME` よりそちらを優先します。そのため引数なしだと、アダプターではなく **Strands の Runtime** を検証します。両方を実施したアカウントでの実測では、`3 passed, 1 failed` と報告され、その失敗は「no spans in aws/spans for travelAgentStrands_travelAgent.DEFAULT」でした。これは Path B について何も語っていません。Path B のサービス名を渡せば、正しい対象を確認します。

```bash
./scripts/verify-telemetry.sh travel-agent-edd-workshop
```

これは `2 passed, 0 failed` と、「Spans are present and the agent log group is empty. That is the normal Path B shape」を表示しました。明示的な引数は、設計上どちらの変数よりも優先されます。
:::

次に、アダプターが生成したトラジェクトリを表示します。`show-trajectory.sh` は同じ任意のサービス名引数を取り、デフォルトの挙動も同じなので、Path A も実施した場合はここでもサービス名を指定してください。

```bash
./scripts/show-trajectory.sh travel-agent-edd-workshop
```

Path B のみのアカウントでは、引数なしの `./scripts/show-trajectory.sh` でも同じです。両方を実施したアカウントでは `RUNTIME_SERVICE_NAME` を読み取り、`Trajectory for travelAgentStrands_travelAgent.DEFAULT ... No spans found.` と表示します。アダプターが失敗したように見えますが、そうではありません。

期待される形。エージェントは非決定的なので、件数と時間は異なります。

```
  span                               kind      sec  model                          tokens in/out
  --------------------------------------------------------------------------------------------
  invoke_agent travel-agent-edd-work AGENT   41.70  -                              -/-
  llm-call-1                         LLM      0.00  -                              -/-
  llm-call-2                         LLM      0.90  us.anthropic.claude-sonnet-4-6 3/77
  execute_tool query_sites           TOOL     0.01  -                              -/-
  llm-call-3                         LLM      0.85  us.anthropic.claude-sonnet-4-6 1911/105
  execute_tool query_sites           TOOL     0.00  -                              -/-
  llm-call-4                         LLM      3.12  us.anthropic.claude-sonnet-4-6 2010/200
  execute_tool plan_route            TOOL     0.01  -                              -/-
  ...
  llm-call-9                         LLM     19.53  us.anthropic.claude-sonnet-4-6 5809/1199

  23 spans across 1 session(s)
    session 62baa681-117f-4651-a: AGENT=1 LLM=9 TOOL=13
```

行はスパンの開始時刻順に並ぶため、ルートの `AGENT` スパンが常に先頭です。含まれるものより先に開始するからです。上の `...` は、その実行の残りの `llm-call-N` と `execute_tool` の行を表します。

:::alert{type="warning" header="no spans found と表示される場合"}
エクスポーターはバッチ処理するため、実行後 30 秒ほど待って再試行してください。空のままなら、`./scripts/verify-telemetry.sh` がどの段階が壊れているかを教えてくれます。
:::

**重要な 3 点を読み取ってください。**

1. **`AGENT=1`** と、0 より大きい `LLM` と `TOOL` の件数。これが、`invoke_agent` だけの平坦なビューでは作れない 3 階層です。
2. 各 `LLM` 行の **呼び出しごとのトークン数**。最後の呼び出しが、ツール選択の呼び出しよりはるかに多い出力トークンを消費していることに注目してください。判断は安く、合成は高価です。
3. **`session.id`** が、すべてのスパンをターミナルでの 1 回の実行に結び付けます。

:::alert{type="info" header="仕組み: なぜ `aws xray get-trace-summaries` を使わないのか"}
Transaction Search が有効な場合、OTLP のスパンは `aws/spans` ロググループに書き込まれ、`xray get-trace-summaries` や `batch-get-traces` では **返されません**。これらのコマンドは、スパンが存在していても何も報告しないことがあるため、代わりに `aws/spans` を読んでください。

上記のようにロググループにクエリするか、コンソールで参照してください: [aws/spans ロググループ](https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/aws$252Fspans)。`aws/spans` は、`input.value` と `output.value` (モジュール 2 が採点するツールの引数と結果) が見える唯一の場所でもあります。
:::

## CloudWatch コンソールで確認する

**期待される結果: エージェントがダッシュボードに現れます。** 実行後、GenAI Observability ダッシュボードに Path B (OpenInference) のエージェントが一覧表示されます。Path A も完了している場合、両方のエージェントが *同じ* ダッシュボードに集まります。Strands のエージェントは `bedrock-agentcore` ランタイムとして、pi-mono のエージェントは `other` として表示され、2 つの計測パスが同じ評価可能な面に到達することを示します。

![期待される結果: 1 つの GenAI Observability ダッシュボードに両方のエージェントが集まり、Path A の Strands エージェントと Path B の pi-mono (OpenInference) エージェントが並んでいる](/static/images/module-1/1b-dashboard-both-agents.png)

:::alert{type="info" header="Path B の行がトークン 0、コストなしと表示される理由"}
Agents テーブルで Path B の行は **Total tokens 0** とコスト列が空になり、Path A の行には実際の数値が表示されます。同じ 0 がトレースのヘッダーにも現れます。テレメトリは問題なく、2 クリックで証明できます。トレースを開き、任意の `llm-call-N` スパンを選ぶと、そのパネルにモデル、`Input tokens`、`Output tokens`、さらにはスパン単位の `Total cost` まで表示されます。

件数はルートではなく `LLM` の子スパンに存在します。アダプターがそこに `llm.token_count.*` として設定し、取り込み時に `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` にもミラーされるため、スパン単位のビューでは価格が計算できます。アダプターが出力するルートの `AGENT` スパンは独自のトークン属性を持たず、エージェントレベルの集計は子の値を合計しないため、テーブルには合計する対象がありません。

`./scripts/show-trajectory.sh` は、同じ呼び出しごとの使用量をスパンから表示します。集計とスパン単位の詳細がこのように食い違うのは、フレームワークを自分で計測したときに現れる典型的な継ぎ目です。スパンを信頼し、ゼロを信じる前に集計が実際に何を読んでいるかを確認してください。
:::

1. AWS コンソールで **CloudWatch** を開き、左ナビゲーションで **GenAI Observability → Bedrock AgentCore** を展開します ([直接リンク](https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#gen-ai-observability/agent-core)。CloudWatch のホームページに飛ぶ場合は、代わりに左ナビゲーションを使ってください)
2. **All traces** タブをクリックします (またはエージェントを開いてその **Traces** タブを開きます)
3. 自分のトレースを見つけます (サービス名 `travel-agent-edd-workshop` でフィルターします)
4. トレースをクリックします。**Spans** パネルが **Tree** で開くので、その隣の **Timeline** トグルをクリックしてウォーターフォールを表示します

タイムラインには LLM 呼び出しとツール実行のウォーターフォールが表示されます。

![X-Ray Timeline Waterfall](/static/images/1f-xray-timeline-waterfall.png)

5. **Quick filter** を **All Events** に設定します。デフォルトは **Agent spans** で、`invoke_agent` と `execute_tool` のグループのみを表示し、`llm-call-N` のスパンをすべて隠します
6. 任意の `llm-call-N` スパンをクリックし (`llm-call-1` は空のものなので、`llm-call-2` 以降を選んでください)、その OpenInference 属性を確認します。

![OpenInference Metadata in X-Ray](/static/images/1f-xray-openinference-metadata.png)

スパンの `attributes` ブロックに、次のものが見えるはずです。
- `openinference.span.kind: "LLM"`
- `llm.model_name: "us.anthropic.claude-sonnet-4-6"`
- 実際の値が入った `llm.token_count.prompt` / `llm.token_count.completion`
- モデルの応答を含む `llm.output_messages`。選択した `tool_call` と渡した引数を含みます

`execute_tool` スパンでは `input.value` (ツールの引数) と `output.value` (ツールの結果) も見えます。これらは、モジュール 2 で AgentCore Evaluation が `ToolParameterAccuracy` と `Faithfulness` のために読む属性です。

**期待される結果: 完全な OpenInference 詳細ビュー。** まとめると、Path B (Strands 以外) のエージェントから開いたトレースには、スパンのツリー、Trajectory グラフ、OpenInference の JSON が並んで表示されるはずです。JSON に `scope = openinference.instrumentation.pi-mono`、`span.kind = AGENT`、`input` / `output` の値、`service.name = travel-agent-edd-workshop` が表示されていることを確認してください。これが、モジュール 2 で AWS がネイティブに評価するスコープです。

![期待される結果: Strands 以外のエージェントの OpenInference トレース詳細。スパンのツリー、Trajectory グラフ、そして scope=openinference.instrumentation.pi-mono、span.kind=AGENT、input/output の値、service.name=travel-agent-edd-workshop を示す JSON](/static/images/module-1/1b-trace-openinference-detail.png)

## トラジェクトリを理解する

トレースはエージェントの推論プロセス全体を明らかにします。上の実行を読むと次のようになります。

| スパン | 所要時間 | トークン入/出 | 起きたこと |
|------|----------|---------------|--------------|
| `invoke_agent travel-agent-edd-work` | 41.70s | -/- | ルートの `AGENT` スパン。呼び出し全体 |
| `llm-call-1` | 0.00s | -/- | 常に空。下の注記を参照 |
| `llm-call-2` | 0.90s | 3/77 | 最初の実際の推論。コーディネーターが `query_sites` を呼ぶと判断。出力 77 トークンはツール呼び出しの JSON だけ |
| `execute_tool query_sites` | 0.01s | -/- | 営業時間、休館日、料金、予約要件を含む観光地を返す |
| `llm-call-3` 〜 `llm-call-8` | 0.83 〜 3.88s | 最大 5040/372 | それ以降のモデルのターンごとに 1 スパン。直前のツール結果を読み、次の呼び出しを決める。結果が蓄積するため入力はターンごとに増える |
| `execute_tool plan_route` | 0.00s | -/- | 休館日を考慮した最適化済みの複数日スケジュール |
| `execute_tool suggest_dining` | 0.00s | -/- | 食事枠のためのレストラン。1 ターンから複数回呼ばれることが多い |
| `llm-call-9` | 19.53s | 5809/1199 | 最終的な合成。整形された旅程 |

この実行は `AGENT=1 LLM=9 TOOL=13` で終わりました。**`LLM` の件数はモデルのターン数を表し、ツール呼び出し数ではありません。** 1 ターンで複数のツール呼び出しを発行できるため、2 つの数値は一致するようには作られていません。

:::alert{type="info" header="毎回 `llm-call-1` が空になる理由"}
アダプターは、ツール結果ではないすべての `message_start` で `LLM` スパンを開きます。そしてフレームワークは、最初の `message_start` を **ユーザー自身のプロンプト** に対して発行し、これにはモデルもトークン使用量もありません。そのため `llm-call-1` は常に 0.00 秒のスパンで、モデルとトークンに `-` を表示し、最初の実際の推論は `llm-call-2` になります。これを除きたい場合は、コードがすでに `"toolResult"` をスキップしているのと同じように、`message_start` のケースで `role === "user"` をスキップしてください。
:::

:::alert{type="info" header="コストに関する洞察"}
`llm-call-9` は、最初のツール選択の呼び出しの 16 倍の出力トークンを使い (1199 対 77)、20 倍以上の時間がかかります。ツール選択は安く、合成は高価です。入力トークンもターンごとに増えます (3、次に 1911、最大 5809)。各ターンが蓄積したツール結果を再送するからです。どちらの事実もトレースには見え、`invoke_agent` だけの平坦なビューには見えません。
:::

:::alert{type="success" header="ここで起きたこと: 因果の連鎖"}
1. **あなたの行動**: 約 200 行のアダプターをエージェントのライフサイクルイベントに購読させました。エージェントのロジックは何も変えていません。
2. **仕組み**: 各ライフサイクルイベントが `openinference.instrumentation.pi-mono` スコープの下で OpenInference のスパン (`AGENT` / `LLM` / `TOOL`) になり、SigV4 で署名されて X-Ray の OTLP エンドポイントに送られました。CloudWatch は同じスパンを `aws/spans` と GenAI Observability ダッシュボードに表示します。
3. **目にした証拠**: 上のトレースのウォーターフォール。そのスパンのタイムスタンプは今実行した呼び出しと一致し、その `execute_tool` の並びこそがエージェントの判断の軌跡です。
4. **原則**: エージェントの可観測性とは、リクエストと応答の対だけでなく *トラジェクトリ* を捕捉することです。そしてトラジェクトリがスパンに入れば、評価は追加コストなしで手に入ります (モジュール 2 はまさにこれらのスパンを採点します)。

**反証チェック:** アダプターなしで (モジュール 0 の状態で) エージェントを実行していたら、この呼び出しについてダッシュボードには何が表示され、それはエージェントが壊れていることを意味したでしょうか。(何も表示されず、そして意味しません。だからこそ「データがない」と「エージェントが悪い」は別の診断です。あなたが証明したのはエージェントだけでなくパイプラインです。)
:::

## チェックポイント: サマリーの前に 2 分

スクラッチファイルに書き出してください。

1. (誰かのスクリーンショットではなく) *あなた* の呼び出しが CloudWatch に到達したという正確な証拠を挙げてください。どのロググループまたはダッシュボードで、どの ID がそれをターミナルでの実行に結び付けますか。
2. 次の原則を完成させてください。「このエージェントに新しいツールが追加されると、その呼び出しはアダプターを変更しなくてもトレースに ___ スパンとして現れる。理由は ___ だから。」
3. ご自身のシステムのうち、現在ツールの判断が見えていないエージェントを持つのはどれですか。それが職場に戻ってからの Path B の候補です。

(2 番目の答えはモジュール 4 で重要になります。そこではコーディングエージェントが新しいツールを追加し、それらがデフォルトで観測可能であってほしくなります。)
