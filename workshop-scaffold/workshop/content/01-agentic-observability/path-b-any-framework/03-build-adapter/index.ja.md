---
title: "Path B.3 アダプターの構築"
weight: 30
---

**シナリオ。** これは Path A では自動で得られるステップです。あなたのフレームワークは OpenTelemetry を出力しないため、ライフサイクルイベントをスパンに変換する小さなアダプターを書きます。**これが存在しない限り、どんなインフラをデプロイしても、観測するものも採点するものもありません。** 同時に、この日構築するなかで最も再利用性が高いものでもあります。ライフサイクルフックを持つフレームワークなら、同じやり方で接続できます。

## プロジェクトのセットアップ

アダプターのプロジェクトを **ワークショップのリポジトリ内**、`travel-agent/` の隣に作成します。ここに置くことで (`~/environment` ではなく)、travel-agent への相対インポートが `src/` から見て安定した `../../travel-agent/...` になります。

```bash
cd /workshop/edd-workshop
mkdir -p openinference-aws-adapter/src && cd openinference-aws-adapter
```

:::alert{type="info" header="➡️ あなたのフレームワークの場合"}
アダプターは独立したプロジェクトであり、pi-mono のエージェントの隣に置く必要はありません。ここで pi-mono 固有なのは、後述の `run.ts` にある `../../travel-agent/` のインポートだけです。ご自身のフレームワークでは、任意の場所にある自前のエージェントをインポートします。このステップのそれ以外 (SigV4 エクスポーター、OTEL のセットアップ、OpenInference の属性名) は、すべての人に共通です。
:::

### `package.json` を作成する

```bash
cat > package.json << 'EOF'
{
  "name": "openinference-aws-adapter",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "start": "tsx src/run.ts"
  },
  "dependencies": {
    "@arizeai/openinference-semantic-conventions": "^2.5.0",
    "@aws-sdk/credential-providers": "^3.374.0",
    "@opentelemetry/api": "^1.9.0",
    "@opentelemetry/resources": "^1.30.0",
    "@opentelemetry/sdk-trace-node": "^1.30.0",
    "@opentelemetry/otlp-transformer": "^0.57.0",
    "dotenv": "^16.4.7"
  },
  "devDependencies": {
    "@types/node": "^22.15.17",
    "tsx": "^4.19.4",
    "typescript": "^5.7.3"
  }
}
EOF
```

```bash
npm install
```

:::alert{type="info" header="ここでの `npm audit` の警告は想定どおりです"}
`npm install` は脆弱性のサマリーで終わります (執筆時点では 9 件: moderate 7 件、high 2 件)。すべて OTEL パッケージの推移的な開発依存関係によるものです。このサンドボックス内のものはインターネットに公開されておらず、このアダプターを配布することもないため、`npm audit fix --force` は実行しないでください。OTEL が非互換のメジャーバージョンに移動し、ビルドが壊れます。
:::

## ステップ 1: SigV4 トレースエクスポーター (`src/sigv4-exporter.ts`)

AWS X-Ray の OTLP エンドポイントは SigV4 のリクエスト署名を要求します。このエクスポーターはスパンを OTLP protobuf にシリアライズし、AWS の認証情報で署名します。

```bash
cat > src/sigv4-exporter.ts << 'EOF'
import { ExportResultCode } from "@opentelemetry/core";
import type { ExportResult } from "@opentelemetry/core";
import type { ReadableSpan, SpanExporter } from "@opentelemetry/sdk-trace-base";
import { ProtobufTraceSerializer } from "@opentelemetry/otlp-transformer";
import { fromNodeProviderChain } from "@aws-sdk/credential-providers";
import crypto from "node:crypto";
import https from "node:https";
import type { AwsCredentialIdentity } from "@smithy/types";

export interface SigV4ExporterConfig {
  url: string;
  region: string;
  service: string;
  headers?: Record<string, string>;
}

function hmac(key: string | Buffer, data: string): Buffer {
  return crypto.createHmac("sha256", key).update(data).digest();
}

function sha256Hex(data: string | Buffer): string {
  return crypto.createHash("sha256").update(data).digest("hex");
}

function getSigningKey(secretKey: string, dateStamp: string, region: string, service: string): Buffer {
  const kDate = hmac("AWS4" + secretKey, dateStamp);
  const kRegion = hmac(kDate, region);
  const kService = hmac(kRegion, service);
  return hmac(kService, "aws4_request");
}

async function signAndSend(
  body: Uint8Array,
  config: SigV4ExporterConfig,
  credentialProvider: () => Promise<AwsCredentialIdentity>
): Promise<void> {
  const parsed = new URL(config.url);
  const hostname = parsed.hostname;
  const path = parsed.pathname;
  const bodyBuffer = Buffer.from(body);

  const creds = await credentialProvider();
  const now = new Date();
  const amzDate = now.toISOString().replace(/[:-]|\.\d{3}/g, "").substring(0, 15) + "Z";
  const dateStamp = amzDate.substring(0, 8);
  const payloadHash = sha256Hex(bodyBuffer);

  const headersToSign: Record<string, string> = {
    "content-type": "application/x-protobuf",
    host: hostname,
    "x-amz-date": amzDate,
    ...(config.headers ?? {}),
  };

  if (creds.sessionToken) {
    headersToSign["x-amz-security-token"] = creds.sessionToken;
  }

  const sortedHeaderNames = Object.keys(headersToSign).sort();
  const canonicalHeaders = sortedHeaderNames.map((k) => `${k}:${headersToSign[k]}`).join("\n") + "\n";
  const signedHeaders = sortedHeaderNames.join(";");

  const canonicalRequest = [
    "POST", path, "", canonicalHeaders, signedHeaders, payloadHash,
  ].join("\n");

  const credentialScope = `${dateStamp}/${config.region}/${config.service}/aws4_request`;
  const stringToSign = [
    "AWS4-HMAC-SHA256", amzDate, credentialScope, sha256Hex(canonicalRequest),
  ].join("\n");

  const signingKey = getSigningKey(creds.secretAccessKey, dateStamp, config.region, config.service);
  const signature = crypto.createHmac("sha256", signingKey).update(stringToSign).digest("hex");
  const authorization = `AWS4-HMAC-SHA256 Credential=${creds.accessKeyId}/${credentialScope}, SignedHeaders=${signedHeaders}, Signature=${signature}`;

  const requestHeaders: Record<string, string> = { ...headersToSign, authorization };

  return new Promise<void>((resolve, reject) => {
    const req = https.request(
      { hostname, path, method: "POST", headers: requestHeaders },
      (res) => {
        let data = "";
        res.on("data", (chunk) => { data += chunk; });
        res.on("end", () => {
          if (res.statusCode && res.statusCode >= 200 && res.statusCode < 300) {
            resolve();
          } else {
            reject(new Error(`OTLP export failed: ${res.statusCode} ${res.statusMessage} - ${data.substring(0, 200)}`));
          }
        });
      }
    );
    req.on("error", reject);
    req.end(bodyBuffer);
  });
}

export class SigV4OtlpTraceExporter implements SpanExporter {
  private readonly config: SigV4ExporterConfig;
  private readonly credentialProvider: () => Promise<AwsCredentialIdentity>;
  private isShutdown = false;

  constructor(config: SigV4ExporterConfig) {
    this.config = config;
    this.credentialProvider = fromNodeProviderChain();
  }

  export(spans: ReadableSpan[], resultCallback: (result: ExportResult) => void): void {
    if (this.isShutdown) {
      resultCallback({ code: ExportResultCode.FAILED });
      return;
    }

    const body = ProtobufTraceSerializer.serializeRequest(spans);
    if (!body) {
      resultCallback({ code: ExportResultCode.FAILED, error: new Error("Failed to serialize spans") });
      return;
    }

    signAndSend(body, this.config, this.credentialProvider)
      .then(() => resultCallback({ code: ExportResultCode.SUCCESS }))
      .catch((error) => {
        process.stderr.write(`[SigV4TraceExporter] ${error}\n`);
        resultCallback({ code: ExportResultCode.FAILED, error: error instanceof Error ? error : new Error(String(error)) });
      });
  }

  async shutdown(): Promise<void> { this.isShutdown = true; }
  async forceFlush(): Promise<void> {}
}
EOF
```

:::alert{type="info" header="なぜ手動で SigV4 を実装するのか"}
X-Ray の OTLP エンドポイントは `UNSIGNED-PAYLOAD` で署名されたリクエストを拒否します (`@smithy/signature-v4` はデフォルトでこれを使います)。これを避けるため、ペイロードの SHA-256 ハッシュを手動で完全に計算しています。このエクスポーターは **フレームワークに依存しません**。何が出力したかに関係なく、アダプターが生成したスパンを署名して送信します。
:::

## ステップ 2: OTEL のセットアップ (`src/otel-setup.ts`)

`createProviders` は、SigV4 エクスポーターに接続された `NodeTracerProvider` を構築します。`aws.log.group.names` リソース属性を設定し、これらのスパンがどのロググループに属するかを AgentCore Observability に伝えます。返すのはスパンだけで、別個のログイベントエクスポーターは **ありません**。評価器は OpenInference のスパンから直接採点するからです。

```bash
cat > src/otel-setup.ts << 'EOF'
import { NodeTracerProvider, BatchSpanProcessor } from "@opentelemetry/sdk-trace-node";
import { Resource } from "@opentelemetry/resources";
import { SigV4OtlpTraceExporter } from "./sigv4-exporter.js";

export interface OtelConfig {
  serviceName: string;
  region: string;
}

export interface OtelProviders {
  tracerProvider: NodeTracerProvider;
}

export function createProviders(config: OtelConfig): OtelProviders {
  // Spans only. The evaluator scores from OpenInference-scoped spans — no
  // separate CloudWatch log-event export is needed. `aws.log.group.names`
  // tells AgentCore Observability which log group these spans belong to.
  const traceExporter = new SigV4OtlpTraceExporter({
    url: `https://xray.${config.region}.amazonaws.com/v1/traces`,
    region: config.region,
    service: "xray",
  });

  const tracerProvider = new NodeTracerProvider({
    resource: new Resource({
      "service.name": config.serviceName,
      "aws.local.service": config.serviceName,
      "aws.service.type": "gen_ai_agent",
      "aws.log.group.names": `/aws/bedrock-agentcore/runtimes/${config.serviceName}`,
    }),
    spanProcessors: [new BatchSpanProcessor(traceExporter)],
  });

  tracerProvider.register();

  return { tracerProvider };
}
EOF
```

## ステップ 3: OpenInference アダプター (`src/openinference-adapter.ts`)

これがトラジェクトリを可視化するアダプターであり、標準 OTEL に欠けていた部分です。エージェントのライフサイクルイベントを購読し、それぞれを OpenInference のスパン種別 (`AGENT` / `LLM` / `TOOL`) にマッピングします。

:::alert{type="info" header="➡️ あなたのフレームワークの場合"}
`agent.subscribe((event) => ...)` のコールバックとイベント名 (`agent_start`、`message_start` / `message_end`、`tool_execution_start` / `tool_execution_end`、`agent_end`) は **pi-mono のライフサイクル API** です。ご自身のフレームワークでは、それに相当するもの (LangChain / LangGraph のコールバック、CrewAI のイベントリスナー、独自エージェントのミドルウェア) にフックし、同じ 3 つの OpenInference スパン種別にマッピングします。OpenInference の属性名 (`openinference.span.kind`、`llm.model_name`、`llm.token_count.*`、`tool.name`、`input.value`、`output.value`) と SigV4 エクスポーターは **すべての人に共通** です。変わるのは `switch` 文のイベント配線部分だけです。
:::

:::alert{type="info" header="1 つのスコープ: 最初から評価に対応"}
アダプターは **すべての** スパン (`AGENT`、`LLM`、`TOOL`) に対して単一のトレーサースコープ `openinference.instrumentation.pi-mono` を使います。AgentCore Evaluation は `openinference.instrumentation.*` のスコープファミリーをネイティブにサポートします。ここで GenAI ダッシュボード向けに出力するスパンそのものが、モジュール 2 で評価器が採点するスパンです。評価器はツール名、引数、結果、最終的な回答をこれらの OpenInference スパンから直接読み取るため、**評価に対応させるための追加作業は何もありません**。2 つ目のスコープも、フレームワークの偽装も、別途出力するログイベントも不要です。
:::

pi-mono のイベントから OpenInference のスパンへの主要なマッピング:

| pi-mono のイベント | OpenInference のスパン | 主な属性 |
|---------------|-------------------|----------------|
| `agent_start` / `agent_end` | `AGENT` (ルート) | `session.id`、`input.value` (クエリ)、`output.value` (最終的な回答) |
| `message_start` / `message_end` | `LLM` (推論ごと) | `llm.model_name`、`llm.token_count.*`、`llm.output_messages` |
| `tool_execution_start` / `tool_execution_end` | `TOOL` | `tool.name`、`gen_ai.tool.name`、`input.value` (引数)、`output.value` (結果) |

`TOOL` スパンの `input.value` (引数) と `output.value` (結果) が、AgentCore Evaluation に `ToolParameterAccuracy` と `Faithfulness` を計算させるものです。`AGENT` スパンの `input.value` / `output.value` は、評価器にユーザーのプロンプトと最終的な回答を与えます。これが 3 階層のトレース階層を生み出します。

```bash
cat > src/openinference-adapter.ts << 'EOF'
import { trace, context, SpanKind, SpanStatusCode, type Span, type Context } from "@opentelemetry/api";
import { OpenInferenceSpanKind } from "@arizeai/openinference-semantic-conventions";
import type { NodeTracerProvider } from "@opentelemetry/sdk-trace-node";

// Single-scope architecture.
//
// AgentCore Evaluation natively supports the OpenInference instrumentation
// scope family: any `openinference.instrumentation.*` scope is recognised by
// the evaluation service's span mapper (matches the on-demand
// Evaluate API — a pi-mono session under this scope scores TrajectoryInOrderMatch,
// ToolParameterAccuracy, ToolSelectionAccuracy and Faithfulness identically to a
// first-class framework like Google ADK). So we emit ONE scope for everything —
// agent, LLM, and tool spans — and the evaluator reads the full trajectory
// (tool names, arguments, results, final answer) straight from the spans.
//
// No Strands-scope impersonation and no separately-emitted CloudWatch log event
// are needed: the evaluator scores from spans alone.
const SCOPE = "openinference.instrumentation.pi-mono";

const MAX_VALUE_LENGTH = 10000;

export interface AdapterConfig {
  agentName: string;
  sessionId: string;
}

export interface AdapterHandle {
  flush: () => Promise<void>;
  unsubscribe: () => void;
  setUserQuery: (q: string) => void;
}

export function instrumentWithOpenInference(
  agent: any,
  config: AdapterConfig,
  provider: NodeTracerProvider
): AdapterHandle {
  // One tracer, one scope. AGENT / LLM / TOOL spans all carry it.
  const tracer = provider.getTracer(SCOPE);

  let traceSpan: Span | undefined;
  let traceCtx: Context | undefined;
  let userQuery = "";

  let currentLlmSpan: Span | undefined;
  let llmCallIndex = 0;

  const toolSpans = new Map<string, Span>();

  const unsubscribe = agent.subscribe((event: any) => {
    switch (event.type) {
      case "agent_start": {
        // Root AGENT span. input.value is the user query; output.value is set
        // on agent_end. The evaluator reads the user prompt + final answer here.
        traceSpan = tracer.startSpan(`invoke_agent ${config.agentName}`, {
          kind: SpanKind.SERVER,
          attributes: {
            "openinference.span.kind": OpenInferenceSpanKind.AGENT,
            "gen_ai.agent.name": config.agentName,
            "session.id": config.sessionId,
            "input.value": userQuery,
          },
        });
        traceCtx = trace.setSpan(context.active(), traceSpan);
        break;
      }

      case "message_start": {
        if (!traceCtx || event.message?.role === "toolResult") break;
        llmCallIndex++;
        // LLM span — one per model inference. This is the visibility OpenInference
        // adds over plain OTEL gen_ai.*: individual model calls are first-class spans.
        currentLlmSpan = tracer.startSpan(`llm-call-${llmCallIndex}`, {
          kind: SpanKind.INTERNAL,
          attributes: {
            "openinference.span.kind": OpenInferenceSpanKind.LLM,
            "session.id": config.sessionId,
          },
        }, traceCtx);
        break;
      }

      case "message_end": {
        if (!currentLlmSpan || !event.message) break;
        const msg = event.message;
        if (msg.model) currentLlmSpan.setAttribute("llm.model_name", msg.model);
        if (msg.usage) {
          const inTok = (msg.usage.input ?? 0) + (msg.usage.cacheRead ?? 0);
          const outTok = msg.usage.output ?? 0;
          currentLlmSpan.setAttribute("llm.token_count.prompt", inTok);
          currentLlmSpan.setAttribute("llm.token_count.completion", outTok);
          currentLlmSpan.setAttribute("llm.token_count.total", inTok + outTok);
        }
        if (Array.isArray(msg.content)) {
          const text = msg.content.filter((b: any) => b?.type === "text").map((b: any) => b.text);
          const tools = msg.content.filter((b: any) => b?.type === "toolCall")
            .map((b: any) => ({ tool_call: { name: b.name, arguments: JSON.stringify(b.arguments) } }));
          const out: any = { role: "assistant" };
          if (text.length) out.content = text.join("");
          if (tools.length) out.tool_calls = tools;
          currentLlmSpan.setAttribute("llm.output_messages", JSON.stringify([out]));
        }
        currentLlmSpan.end();
        currentLlmSpan = undefined;
        break;
      }

      case "tool_execution_start": {
        if (!traceCtx) break;
        // TOOL span. input.value = arguments (the evaluator reads these for
        // ToolParameterAccuracy); output.value is filled on tool_execution_end
        // (Faithfulness reads it to check the answer is grounded in tool results).
        const s = tracer.startSpan(`execute_tool ${event.toolName}`, {
          kind: SpanKind.INTERNAL,
          attributes: {
            "openinference.span.kind": OpenInferenceSpanKind.TOOL,
            "tool.name": event.toolName,
            "gen_ai.tool.name": event.toolName,
            "input.value": JSON.stringify(event.args ?? {}),
            "session.id": config.sessionId,
          },
        }, traceCtx);
        toolSpans.set(event.toolCallId, s);
        break;
      }

      case "tool_execution_end": {
        const s = toolSpans.get(event.toolCallId);
        if (s) {
          const output = extractToolOutput(event);
          if (output) s.setAttribute("output.value", output.slice(0, MAX_VALUE_LENGTH));
          if (event.isError) s.setStatus({ code: SpanStatusCode.ERROR });
          s.end();
          toolSpans.delete(event.toolCallId);
        }
        break;
      }

      case "agent_end": {
        for (const [, s] of toolSpans) s.end();
        toolSpans.clear();
        if (currentLlmSpan) { currentLlmSpan.end(); currentLlmSpan = undefined; }

        if (traceSpan) {
          if (userQuery) traceSpan.setAttribute("input.value", userQuery);
          const resp = extractResponse(event.messages);
          if (resp) traceSpan.setAttribute("output.value", resp.slice(0, MAX_VALUE_LENGTH));
          traceSpan.end();
          traceSpan = undefined;
          traceCtx = undefined;
        }
        break;
      }
    }
  });

  return {
    flush: async () => {
      await provider.forceFlush();
    },
    unsubscribe,
    setUserQuery: (q) => { userQuery = q; },
  };
}

function extractToolOutput(event: any): string {
  const r = event?.result ?? event?.output ?? event?.toolResult;
  if (r == null) return "";
  if (typeof r === "string") return r;
  try { return JSON.stringify(r); } catch { return String(r); }
}

function extractResponse(msgs: any[]): string {
  if (!msgs) return "";
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i]?.role === "assistant" && Array.isArray(msgs[i].content))
      return msgs[i].content.filter((b: any) => b?.type === "text").map((b: any) => b.text).join("");
  }
  return "";
}
EOF
```

## ステップ 4: エントリーポイント (`src/run.ts`)

エントリーポイントは、モジュール 0 ですでに実行した **既存の** `travel-agent` をインポートし (`../../travel-agent/src/coordinator.js` と `.../utils/config.js` はクローン済みリポジトリの一部で、ここで作成するものではありません)、今構築したアダプターでラップします。

```bash
cat > src/run.ts << 'EOF'
import "dotenv/config";
import { randomUUID } from "crypto";
import { createCoordinatorAgent } from "../../travel-agent/src/coordinator.js";
import { loadConfig as loadTravelAgentConfig } from "../../travel-agent/src/utils/config.js";
import { createProviders } from "./otel-setup.js";
import { instrumentWithOpenInference } from "./openinference-adapter.js";

async function main(): Promise<void> {
  const agentName = process.env.AGENT_NAME ?? "travel-agent-edd-workshop";
  const region = process.env.AWS_REGION ?? "us-east-1";
  const sessionId = process.env.SESSION_ID ?? randomUUID();
  const userQuery = process.env.USER_QUERY ??
    "Plan a 3-day trip to Luminara with cultural sites and local dining";

  const { tracerProvider } = createProviders({ serviceName: agentName, region });

  const travelAgentConfig = loadTravelAgentConfig();
  const agent = createCoordinatorAgent(travelAgentConfig);

  const adapter = instrumentWithOpenInference(agent, { agentName, sessionId }, tracerProvider);
  adapter.setUserQuery(userQuery);

  console.log(`[run] Agent: ${agentName}`);
  console.log(`[run] Session: ${sessionId}`);
  console.log(`[run] Region: ${region}`);
  console.log(`[run] Scope: openinference.instrumentation.pi-mono`);
  console.log(`[run] Traces → xray.${region}.amazonaws.com`);
  console.log(`[run] Query: "${userQuery}"\n`);

  await agent.prompt(userQuery);

  const messages = agent.state.messages;
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i]?.role === "assistant") {
      const text = messages[i].content
        .filter((c: any) => c.type === "text")
        .map((c: any) => c.text)
        .join("");
      console.log("--- Agent Response ---\n");
      console.log(text.slice(0, 1000));
      if (text.length > 1000) console.log("\n... (truncated)");
      break;
    }
  }

  console.log("\n[run] Flushing spans...");
  await adapter.flush();
  console.log("[run] Done.");
  console.log("[run] - Traces + full trajectory: CloudWatch GenAI Observability");
  console.log("[run] - AgentCore Online Eval scores these spans directly (Module 2)");

  process.exit(0);
}

main().catch((err) => {
  // Print the whole error, not just .message: the OTLP exporter rejects with a
  // non-Error value, so `err.message` alone prints "undefined" and hides the cause.
  const detail = err?.message ?? (typeof err === "string" ? err : JSON.stringify(err));
  console.error(`[run] Fatal: ${detail}`);
  if (String(detail).includes("Trace Segment Destination")) {
    console.error(
      "[run] Cause: CloudWatch Transaction Search is not ACTIVE yet.\n" +
      "[run] Check:  aws xray get-trace-segment-destination --region us-east-1\n" +
      "[run] Wait for Status=ACTIVE (a few minutes after the Path B.2 stack finishes), then re-run."
    );
  }
  process.exit(1);
});
EOF
```

:::alert{type="info" header="➡️ あなたのフレームワークの場合"}
`../../travel-agent/...` のインポート (`createCoordinatorAgent`、`loadTravelAgentConfig`) は **pi-mono 固有** で、このワークショップのサンプルエージェントのものです。ご自身のフレームワークでは、代わりにここで自前のエージェントをインポートして生成し、`instrumentWithOpenInference(agent, ...)` に渡します。プロバイダーを作成し、エージェントを計測し、実行し、フラッシュするという配線はそのままです。
:::

## ステップ 5: 環境変数

```bash
cat > .env << 'EOF'
AWS_REGION=us-east-1
AGENT_NAME=travel-agent-edd-workshop
MODEL_ID=us.anthropic.claude-sonnet-4-6
USER_QUERY="Plan a 3-day trip to Luminara with cultural sites and local dining"
EOF
```

外部プラットフォームのキーは不要です。認証には EC2 インスタンスの IAM ロール (またはローカルの AWS 認証情報) を使います。

これで 4 つのソースファイル (`sigv4-exporter.ts`、`otel-setup.ts`、`openinference-adapter.ts`、`run.ts`) と `package.json`、`.env` を作成しました。まだ何も実行しません。それが次のステップです。

**次: Path B.4 実行と確認**。計測されたエージェントを実行し (`npm start`)、トレースと `invoke_agent` ログイベントが CloudWatch に届くことを確認します。
