// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

// Experiment runner — runs the cases against the Coordinator and produces a
// markdown report + machine-readable JSON.
//
// Two evaluators run for each case:
//   1. TrajectoryEvaluator — does the actual tool-call sequence match what
//      the case expects?
//   2. LLM-as-Judge (judge.ts) — does the response satisfy the case rubric?
//
// Use this for the model-swap (Module 3.2) and prompt-change (Module 3.3)
// exercises: run once with the baseline model, change one variable, run
// again, diff the trajectory and content columns.
//
// Agents are non-deterministic, so a single run of a single case is a weak
// signal. Before you conclude a change caused a regression, CONFIRM it is
// real by re-running just the suspect case several times:
//
//   --case <substring>   run only cases whose name contains <substring>
//   --runs <N>           run each selected case N times (default 1) and
//                        report stability: STABLE PASS (N/N), FLAKY (k/N),
//                        or STABLE FAIL (0/N), plus content min/mean/max
//
// Usage:
//   npx tsx eval/run-experiment.ts --output results/baseline.md
//   MODEL_ID=us.amazon.nova-lite-v1:0 npx tsx eval/run-experiment.ts --output results/nova.md
//   npx tsx eval/run-experiment.ts --case 2day_history --runs 5 --output results/confirm.md

import { writeFile, mkdir } from "node:fs/promises";
import { dirname } from "node:path";
import { createCoordinatorAgent } from "../src/coordinator.js";
import { loadConfig, withRetry } from "../src/utils/config.js";
import { CASES, type Case } from "./cases.js";
import { extractTrajectory, matchTrajectory } from "./trajectory.js";
import { judgeResponse } from "./judge.js";

interface CaseResult {
  case: Case;
  trajectory: ReturnType<typeof matchTrajectory>;
  judge: { score: number; reason: string };
  must_contain_passed: boolean;
  must_not_contain_passed: boolean;
  response: string;
  error?: string;
  duration_ms: number;
}

async function runCase(c: Case): Promise<CaseResult> {
  const config = loadConfig();
  const agent = createCoordinatorAgent(config);
  const start = Date.now();
  try {
    await withRetry(() => agent.prompt(c.prompt));
    const messages = agent.state.messages;
    const lastAssistant = [...messages]
      .reverse()
      .find((m) => m && "role" in m && m.role === "assistant") as { content: { type: string; text?: string }[] } | undefined;
    const response =
      lastAssistant?.content
        .filter((p) => p.type === "text")
        .map((p) => p.text || "")
        .join("") ?? "";

    const actual = extractTrajectory(agent);
    const trajectory = matchTrajectory(actual, c.expected_trajectory, c.trajectory_match);

    const judge = await judgeResponse(c.rubric, c.prompt, response);

    const must_contain_passed = (c.must_contain ?? []).every((s) =>
      response.toLowerCase().includes(s.toLowerCase())
    );
    const must_not_contain_passed = (c.must_not_contain ?? []).every(
      (s) => !response.toLowerCase().includes(s.toLowerCase())
    );

    return {
      case: c,
      trajectory,
      judge: { score: judge.score, reason: judge.reason },
      must_contain_passed,
      must_not_contain_passed,
      response,
      duration_ms: Date.now() - start,
    };
  } catch (err) {
    return {
      case: c,
      trajectory: { actual: [], expected: c.expected_trajectory, mode: c.trajectory_match, passed: false, reason: "error" },
      judge: { score: 0, reason: "error" },
      must_contain_passed: false,
      must_not_contain_passed: false,
      response: "",
      error: err instanceof Error ? err.message : String(err),
      duration_ms: Date.now() - start,
    };
  }
}

function escapePipe(s: string): string {
  return s.replace(/\|/g, "\\|").replace(/\n/g, " ");
}

function renderMarkdown(model: string, results: CaseResult[]): string {
  const trajPass = results.filter((r) => r.trajectory.passed).length;
  const judgeAvg = results.reduce((s, r) => s + r.judge.score, 0) / Math.max(1, results.length);
  const lines: string[] = [];
  lines.push(`# Eval report — ${model}`);
  lines.push("");
  lines.push(`Cases: ${results.length}`);
  lines.push(`Trajectory pass rate: ${trajPass}/${results.length}`);
  lines.push(`Average content score: ${judgeAvg.toFixed(2)}`);
  lines.push("");
  lines.push("| Case | Trajectory | Content | must_contain | must_not_contain | Duration |");
  lines.push("| --- | --- | --- | --- | --- | --- |");
  for (const r of results) {
    lines.push(
      `| ${r.case.name} | ${r.trajectory.passed ? "PASS" : "FAIL"} | ${r.judge.score.toFixed(2)} | ${r.must_contain_passed ? "PASS" : "FAIL"} | ${r.must_not_contain_passed ? "PASS" : "FAIL"} | ${(r.duration_ms / 1000).toFixed(1)}s |`
    );
  }
  lines.push("");
  lines.push("## Per-case detail");
  for (const r of results) {
    lines.push(`### ${r.case.name}`);
    lines.push(`- Prompt: ${escapePipe(r.case.prompt)}`);
    lines.push(`- Trajectory expected (${r.trajectory.mode}): ${JSON.stringify(r.trajectory.expected)}`);
    lines.push(`- Trajectory actual: ${JSON.stringify(r.trajectory.actual)}`);
    lines.push(`- Trajectory match: ${r.trajectory.passed ? "PASS" : "FAIL"} — ${r.trajectory.reason}`);
    lines.push(`- Content score: ${r.judge.score.toFixed(2)} — ${r.judge.reason}`);
    if (r.error) lines.push(`- Error: ${r.error}`);
    lines.push("");
  }
  return lines.join("\n");
}

function parseArgs(argv: string[]): {
  output: string;
  jsonOutput?: string;
  includeTimeEstimator: boolean;
  caseFilter?: string;
  runs: number;
} {
  let output = "results/eval.md";
  let jsonOutput: string | undefined;
  let includeTimeEstimator = false;
  let caseFilter: string | undefined;
  let runs = 1;
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--output" && argv[i + 1]) output = argv[++i];
    else if (argv[i] === "--json-output" && argv[i + 1]) jsonOutput = argv[++i];
    else if (argv[i] === "--case" && argv[i + 1]) caseFilter = argv[++i];
    else if (argv[i] === "--runs" && argv[i + 1]) runs = Math.max(1, parseInt(argv[++i], 10) || 1);
    // Opt-in: also run the 5 time_estimator cases (they exercise the
    // time_estimator tool, not the core trajectory lesson). The workshop
    // Module 3 walkthrough uses the 6 default Luminara cases only.
    else if (argv[i] === "--include-time-estimator" || argv[i] === "--all") includeTimeEstimator = true;
  }
  return { output, jsonOutput, includeTimeEstimator, caseFilter, runs };
}

// Multi-run stability report. Agents are non-deterministic; one run of one
// case cannot distinguish a real regression from noise. This renders, per
// case, the trajectory outcome of every run plus min/mean/max of the content
// score, and a verdict:
//   STABLE PASS (N/N)  — treat as green
//   STABLE FAIL (0/N)  — a real regression, go fix it
//   FLAKY (k/N)        — the case is sensitive to sampling; tighten the
//                        prompt/rubric or accept the variance consciously
function renderStabilityMarkdown(model: string, runsPerCase: Map<string, CaseResult[]>): string {
  const lines: string[] = [];
  lines.push(`# Eval stability report — ${model}`);
  lines.push("");
  lines.push("| Case | Trajectory | Content min / mean / max | Verdict |");
  lines.push("| --- | --- | --- | --- |");
  for (const [name, rs] of runsPerCase) {
    const passes = rs.filter((r) => r.trajectory.passed).length;
    const scores = rs.map((r) => r.judge.score);
    const min = Math.min(...scores);
    const max = Math.max(...scores);
    const mean = scores.reduce((s, v) => s + v, 0) / scores.length;
    const verdict =
      passes === rs.length ? `STABLE PASS (${passes}/${rs.length})`
      : passes === 0 ? `STABLE FAIL (0/${rs.length})`
      : `FLAKY (${passes}/${rs.length})`;
    lines.push(
      `| ${name} | ${passes}/${rs.length} | ${min.toFixed(2)} / ${mean.toFixed(2)} / ${max.toFixed(2)} | ${verdict} |`
    );
  }
  lines.push("");
  lines.push("## Per-run detail");
  for (const [name, rs] of runsPerCase) {
    lines.push(`### ${name}`);
    rs.forEach((r, i) => {
      lines.push(
        `- run ${i + 1}: traj=${r.trajectory.passed ? "PASS" : "FAIL"} (${JSON.stringify(r.trajectory.actual)}), content=${r.judge.score.toFixed(2)} — ${escapePipe(r.judge.reason)}`
      );
    });
    lines.push("");
  }
  lines.push("## How to read this");
  lines.push("- STABLE FAIL after a change you made = a real regression. Revert or fix, then re-run.");
  lines.push("- FLAKY = the failure reproduces only sometimes. Do NOT ship a conclusion off one run — either tighten the case (more specific prompt/rubric) or fix the agent behavior that makes it sensitive.");
  lines.push("- A content-score swing bigger than ~0.15 across identical runs means the judge, not the agent, may be the noise source — check the rubric for vague words.");
  return lines.join("\n");
}

async function main(): Promise<void> {
  const { output, jsonOutput, includeTimeEstimator, caseFilter, runs } = parseArgs(process.argv.slice(2));
  const config = loadConfig();
  const allCases: Case[] = [...CASES];
  // The time_estimator cases are built by the participant in Module 4.4
  // (test-first, via the edd-driven-agent-dev Power). They are loaded lazily
  // so `--all` works both before the file exists (core cases only, with a
  // note) and after the participant creates eval/cases-time-estimator.ts.
  if (includeTimeEstimator) {
    try {
      const mod = await import("./cases-time-estimator.js");
      if (Array.isArray(mod.TIME_ESTIMATOR_CASES)) allCases.push(...mod.TIME_ESTIMATOR_CASES);
    } catch {
      console.log(
        "Note: eval/cases-time-estimator.ts not found — running the core cases only. " +
          "You build the time_estimator cases in Module 4.",
      );
    }
  }
  const selected = caseFilter
    ? allCases.filter((c) => c.name.includes(caseFilter))
    : allCases;
  if (selected.length === 0) {
    console.error(`No cases match --case "${caseFilter}". Available: ${allCases.map((c) => c.name).join(", ")}`);
    process.exit(1);
  }

  console.log(
    `Running ${selected.length} case(s) x ${runs} run(s) against ${config.modelId}` +
      (caseFilter ? ` (filter: "${caseFilter}")` : "")
  );
  const results: CaseResult[] = [];
  const runsPerCase = new Map<string, CaseResult[]>();
  for (const c of selected) {
    for (let i = 0; i < runs; i++) {
      process.stdout.write(`  ${c.name}${runs > 1 ? ` [run ${i + 1}/${runs}]` : ""} ... `);
      const r = await runCase(c);
      results.push(r);
      if (!runsPerCase.has(c.name)) runsPerCase.set(c.name, []);
      runsPerCase.get(c.name)!.push(r);
      process.stdout.write(`traj=${r.trajectory.passed ? "PASS" : "FAIL"} score=${r.judge.score.toFixed(2)}\n`);
    }
  }

  const markdown =
    runs > 1
      ? renderStabilityMarkdown(config.modelId, runsPerCase)
      : renderMarkdown(config.modelId, results);
  await mkdir(dirname(output), { recursive: true });
  await writeFile(output, markdown);
  console.log(`\nReport: ${output}`);

  if (jsonOutput) {
    await mkdir(dirname(jsonOutput), { recursive: true });
    await writeFile(
      jsonOutput,
      JSON.stringify(
        {
          model: config.modelId,
          results: results.map((r) => ({
            name: r.case.name,
            trajectory_passed: r.trajectory.passed,
            trajectory_actual: r.trajectory.actual,
            trajectory_expected: r.trajectory.expected,
            content_score: r.judge.score,
            content_reason: r.judge.reason,
            must_contain_passed: r.must_contain_passed,
            must_not_contain_passed: r.must_not_contain_passed,
            duration_ms: r.duration_ms,
            error: r.error,
          })),
        },
        null,
        2
      )
    );
    console.log(`JSON: ${jsonOutput}`);
  }
}

main().catch((err) => {
  console.error("Fatal:", err instanceof Error ? err.message : err);
  process.exit(1);
});
