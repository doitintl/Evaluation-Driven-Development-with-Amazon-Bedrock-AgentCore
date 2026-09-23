// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

// Trajectory extraction + matching.
//
// Extracts the sequence of tool names invoked by the Coordinator from the
// agent's message history, then matches against the case's expected
// trajectory under one of four modes (aligned with industry standards):
//
//   - superset:  every expected tool must appear at least once (extra calls OK)
//                ≡ Strands any_order_match, AgentCore TrajectoryAnyOrderMatch, LangSmith Superset
//   - in_order:  expected tools must appear in order (extra calls between them OK)
//                ≡ Strands in_order_match, AgentCore TrajectoryInOrderMatch
//   - exact:     actual sequence must equal expected exactly (no extras, no order changes)
//                ≡ Strands exact_match, AgentCore TrajectoryExactOrderMatch, LangSmith Strict
//   - subset:    actual tools are a subset of expected (no unexpected tools allowed;
//                repeats of expected tools are fine, only `exact` objects to those)
//                ≡ LangSmith Subset — catches over-planning: tools the request did not need

import type { Agent } from "@mariozechner/pi-agent-core";
import type { TrajectoryMatchMode } from "./cases.js";

export interface TrajectoryResult {
  actual: string[];
  expected: string[];
  mode: TrajectoryMatchMode;
  passed: boolean;
  reason: string;
}

export function extractTrajectory(agent: Agent): string[] {
  const calls: string[] = [];
  for (const msg of agent.state.messages) {
    if (!msg || !("role" in msg) || msg.role !== "assistant") continue;
    for (const part of msg.content) {
      if (part && (part as { type?: string }).type === "toolCall") {
        const tc = part as { type: "toolCall"; name: string };
        calls.push(tc.name);
      }
    }
  }
  return calls;
}

export function matchTrajectory(
  actual: string[],
  expected: string[],
  mode: TrajectoryMatchMode
): TrajectoryResult {
  if (mode === "exact") {
    const passed =
      actual.length === expected.length &&
      actual.every((a, i) => a === expected[i]);
    return {
      actual,
      expected,
      mode,
      passed,
      reason: passed
        ? "exact match"
        : `expected exact ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`,
    };
  }

  if (mode === "in_order") {
    let i = 0;
    for (const a of actual) {
      if (i < expected.length && a === expected[i]) i++;
    }
    const passed = i === expected.length;
    return {
      actual,
      expected,
      mode,
      passed,
      reason: passed
        ? "all expected tools appeared in order"
        : `expected ${JSON.stringify(expected)} in order, got ${JSON.stringify(actual)}`,
    };
  }

  if (mode === "subset") {
    const expectedSet = new Set(expected);
    const unexpected = actual.filter((a) => !expectedSet.has(a));
    const passed = unexpected.length === 0;
    return {
      actual,
      expected,
      mode,
      passed,
      reason: passed
        ? "all actual tools are within the expected set"
        : `unexpected tool calls: ${JSON.stringify(unexpected)}; only ${JSON.stringify(expected)} are allowed`,
    };
  }

  // superset (default) — agent must call at least all expected tools
  const missing = expected.filter((e) => !actual.includes(e));
  const passed = missing.length === 0;
  return {
    actual,
    expected,
    mode,
    passed,
    reason: passed
      ? "all expected tools called"
      : `missing tool calls: ${JSON.stringify(missing)}; actual: ${JSON.stringify(actual)}`,
  };
}
