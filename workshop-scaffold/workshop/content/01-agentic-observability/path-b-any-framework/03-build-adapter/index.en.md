---
title: "Path B.3 Build the Adapter"
weight: 30
---

**Scenario.** This is the step Path A gets for free. Your framework emits no
OpenTelemetry, so you write a small adapter that turns its lifecycle events into
spans. **Until it exists there is nothing to observe and nothing to score**, no
matter what infrastructure is deployed. It is also the most reusable thing you
build all day: any framework with lifecycle hooks can be wired the same way.

## Project Setup

Create the adapter project **inside the workshop repo**, alongside `travel-agent/`. Keeping it here (rather than in `~/environment`) means the relative import to the travel-agent is a stable `../../travel-agent/...` from `src/`.

```bash
cd /workshop/edd-workshop
mkdir -p openinference-aws-adapter/src && cd openinference-aws-adapter
```

:::alert{type="info" header="➡️ For your framework"}
The adapter is a standalone project, it does not have to live next to a pi-mono agent. The only pi-mono-specific detail here is the `../../travel-agent/` import in `run.ts` (below). For your framework you import your own agent instead, from wherever it lives. Everything else in this step, the SigV4 exporter, the OTEL setup, the OpenInference attribute names: is identical for everyone.
:::

### Create `package.json`

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

:::alert{type="info" header="`npm audit` warnings here are expected"}
`npm install` finishes with a vulnerability summary (9 at the time of writing: 7 moderate,
2 high), all from transitive dev dependencies of the OTEL packages. Nothing in this
sandbox is internet-facing and you are not shipping this adapter, so do not run
`npm audit fix --force`: it will move OTEL to incompatible majors and break the build.
:::

## Step 1: SigV4 Trace Exporter (`src/sigv4-exporter.ts`)

AWS X-Ray's OTLP endpoint requires SigV4 request signing. This exporter serializes spans to OTLP protobuf and signs them with your AWS credentials.

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

:::alert{type="info" header="Why manual SigV4?"}
The X-Ray OTLP endpoint rejects requests signed with `UNSIGNED-PAYLOAD` (which `@smithy/signature-v4` uses by default). We compute the full SHA-256 payload hash manually to avoid this. This exporter is **framework-agnostic**: it signs and ships whatever spans the adapter produces, regardless of what emitted them.
:::

## Step 2: OTEL Setup (`src/otel-setup.ts`)

`createProviders` builds a `NodeTracerProvider` wired to the SigV4 exporter. It sets the `aws.log.group.names` resource attribute so AgentCore Observability knows which log group these spans belong to. Note it returns spans only, there is **no** separate log-event exporter, because the evaluator scores directly from the OpenInference spans.

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

## Step 3: OpenInference Adapter (`src/openinference-adapter.ts`)

This is the adapter that makes the trajectory visible: the piece that standard OTEL was missing. It subscribes to the agent's lifecycle events and maps each one to an OpenInference span kind (`AGENT` / `LLM` / `TOOL`).

:::alert{type="info" header="➡️ For your framework"}
The `agent.subscribe((event) => ...)` callback and the event names (`agent_start`, `message_start` / `message_end`, `tool_execution_start` / `tool_execution_end`, `agent_end`) are **pi-mono's lifecycle API**. For your framework you hook its equivalent, LangChain/LangGraph callbacks, CrewAI event listeners, or your custom agent's middleware, and map them to the same three OpenInference span kinds. The OpenInference attribute names (`openinference.span.kind`, `llm.model_name`, `llm.token_count.*`, `tool.name`, `input.value`, `output.value`) and the SigV4 exporter are **identical for everyone**. Only the event-plumbing in the `switch` statement changes.
:::

:::alert{type="info" header="One scope: natively evaluation-ready"}
The adapter uses a single tracer scope, `openinference.instrumentation.pi-mono`, for **all** spans (`AGENT`, `LLM`, and `TOOL`). AgentCore Evaluation natively supports the `openinference.instrumentation.*` scope family: the exact spans you emit here for the GenAI dashboard are the spans the evaluator scores in Module 2. It reads tool names, arguments, results, and the final answer straight from these OpenInference spans, so there is **nothing extra to do to become evaluation-ready**. No second scope, no framework impersonation, no separately-emitted log event.
:::

The key mapping from pi-mono events to OpenInference spans:

| pi-mono Event | OpenInference Span | Key Attributes |
|---------------|-------------------|----------------|
| `agent_start` / `agent_end` | `AGENT` (root) | `session.id`, `input.value` (query), `output.value` (final answer) |
| `message_start` / `message_end` | `LLM` (per inference) | `llm.model_name`, `llm.token_count.*`, `llm.output_messages` |
| `tool_execution_start` / `tool_execution_end` | `TOOL` | `tool.name`, `gen_ai.tool.name`, `input.value` (args), `output.value` (result) |

The `TOOL` span's `input.value` (arguments) and `output.value` (result) are what let AgentCore Evaluation compute `ToolParameterAccuracy` and `Faithfulness`; the `AGENT` span's `input.value` / `output.value` give the evaluator the user prompt and final answer. This is what produces the three-level trace hierarchy:

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

## Step 4: Entry Point (`src/run.ts`)

The entry point imports the **existing** `travel-agent` you already ran in Module 0 (`../../travel-agent/src/coordinator.js` and `.../utils/config.js` are part of the cloned repo, you don't create them here) and wraps it with the adapter you just built.

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

:::alert{type="info" header="➡️ For your framework"}
The `../../travel-agent/...` imports (`createCoordinatorAgent`, `loadTravelAgentConfig`) are **pi-mono-specific**: that's this workshop's example agent. For your framework, import and construct your own agent here instead, then pass it to `instrumentWithOpenInference(agent, ...)`. The wiring, create providers, instrument the agent, run it, flush, stays the same.
:::

## Step 5: Environment Variables

```bash
cat > .env << 'EOF'
AWS_REGION=us-east-1
AGENT_NAME=travel-agent-edd-workshop
MODEL_ID=us.anthropic.claude-sonnet-4-6
USER_QUERY="Plan a 3-day trip to Luminara with cultural sites and local dining"
EOF
```

No external platform keys needed: authentication uses your EC2 instance's IAM role (or local AWS credentials).

You've now created all four source files (`sigv4-exporter.ts`, `otel-setup.ts`, `openinference-adapter.ts`, `run.ts`) plus `package.json` and `.env`. You don't run anything yet, that's the next step.

**Next: Path B.4 Run and Verify**: you'll run the instrumented agent (`npm start`) and confirm the traces and the `invoke_agent` log event land in CloudWatch.
