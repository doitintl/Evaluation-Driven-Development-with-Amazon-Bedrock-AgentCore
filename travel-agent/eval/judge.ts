// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

// LLM-as-Judge content evaluator.
//
// Scores a response against a rubric on a 0.0–1.0 scale, returning the
// score plus a one-sentence justification. The judge model is independent
// from the model under test so the score reflects the rubric, not the
// generator's own bias.

import { getModel } from "@mariozechner/pi-ai";
import { completeSimple } from "@mariozechner/pi-ai";

export interface JudgeResult {
  score: number;
  reason: string;
  raw: string;
}

const JUDGE_SYSTEM_PROMPT = `You are an evaluation judge for AI agent responses. Score the response against the rubric on a strict 0.0 to 1.0 scale.

Output FORMAT (exactly two lines):
SCORE: <number between 0.0 and 1.0, two decimals>
REASON: <one sentence explaining the score>

Scoring guide:
- 1.0: rubric fully satisfied, no constraint violations
- 0.7–0.9: minor omissions or wording issues, no constraint violations
- 0.4–0.6: partial satisfaction OR a single low-severity constraint violation
- 0.1–0.3: major omissions OR clear constraint violation (e.g., scheduling a closed attraction)
- 0.0: rubric not addressed or completely wrong response

Be strict. Do not award points for surface fluency.`;

// Default judge: Sonnet 4.6 via the global. inference profile so AgentCore
// Online Eval can use the same string. Sonnet 4.5 is deprecated; do not
// pin to it. To swap to Nova for cost or to a different Claude version,
// pass the second arg or set MODEL_ID-style overrides upstream.
export async function judgeResponse(
  rubric: string,
  prompt: string,
  response: string,
  judgeModelId: string = "global.anthropic.claude-sonnet-4-6"
): Promise<JudgeResult> {
  const model = getModel("amazon-bedrock", judgeModelId as any);
  if (!model) {
    throw new Error(`Judge model "${judgeModelId}" not found in pi-ai registry`);
  }

  const userMessage = [
    "## User prompt",
    prompt,
    "",
    "## Rubric",
    rubric,
    "",
    "## Agent response",
    response,
  ].join("\n");

  const result = await completeSimple(model, {
    systemPrompt: JUDGE_SYSTEM_PROMPT,
    messages: [{ role: "user", content: [{ type: "text", text: userMessage }], timestamp: Date.now() }],
  });

  const raw = result.content
    .filter((c): c is { type: "text"; text: string } => c.type === "text")
    .map((c) => c.text)
    .join("");

  const scoreMatch = raw.match(/SCORE:\s*([0-9.]+)/i);
  const reasonMatch = raw.match(/REASON:\s*(.+?)(?:\n|$)/i);

  const score = scoreMatch ? Math.min(1, Math.max(0, parseFloat(scoreMatch[1]))) : 0;
  const reason = reasonMatch ? reasonMatch[1].trim() : "Judge output missing REASON line.";

  return { score, reason, raw };
}
