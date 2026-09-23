// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

// Unit tests for the trajectory matcher.
//
// These run on every `npm test` and protect the matching semantics that
// Modules 2.1 and 2.2 lean on. Live LLM evaluation runs separately via
// `npx tsx eval/run-experiment.ts` because it requires AWS credentials.

import { describe, it, expect } from "vitest";
import { matchTrajectory } from "../../eval/trajectory.js";

describe("matchTrajectory", () => {
  describe("superset", () => {
    it("passes when all expected tools appear", () => {
      const r = matchTrajectory(
        ["query_sites", "plan_route", "suggest_dining"],
        ["query_sites", "plan_route", "suggest_dining"],
        "superset"
      );
      expect(r.passed).toBe(true);
    });

    it("passes when expected tools appear in different order", () => {
      const r = matchTrajectory(
        ["plan_route", "suggest_dining", "query_sites"],
        ["query_sites", "plan_route", "suggest_dining"],
        "superset"
      );
      expect(r.passed).toBe(true);
    });

    it("passes when extra calls appear alongside expected", () => {
      const r = matchTrajectory(
        ["query_sites", "query_sites", "plan_route", "suggest_dining"],
        ["query_sites", "plan_route", "suggest_dining"],
        "superset"
      );
      expect(r.passed).toBe(true);
    });

    it("fails when an expected tool is missing", () => {
      const r = matchTrajectory(
        ["query_sites", "plan_route"],
        ["query_sites", "plan_route", "suggest_dining"],
        "superset"
      );
      expect(r.passed).toBe(false);
      expect(r.reason).toContain("suggest_dining");
    });
  });

  describe("in_order", () => {
    it("passes when expected tools appear in order", () => {
      const r = matchTrajectory(
        ["query_sites", "plan_route", "suggest_dining"],
        ["query_sites", "plan_route", "suggest_dining"],
        "in_order"
      );
      expect(r.passed).toBe(true);
    });

    it("passes when extra calls appear between expected tools", () => {
      const r = matchTrajectory(
        ["query_sites", "query_sites", "plan_route", "query_sites", "suggest_dining"],
        ["query_sites", "plan_route", "suggest_dining"],
        "in_order"
      );
      expect(r.passed).toBe(true);
    });

    it("fails when expected tools are out of order", () => {
      const r = matchTrajectory(
        ["plan_route", "query_sites", "suggest_dining"],
        ["query_sites", "plan_route", "suggest_dining"],
        "in_order"
      );
      expect(r.passed).toBe(false);
    });
  });

  describe("exact", () => {
    it("passes only on identical sequences", () => {
      const r = matchTrajectory(
        ["query_sites", "plan_route", "suggest_dining"],
        ["query_sites", "plan_route", "suggest_dining"],
        "exact"
      );
      expect(r.passed).toBe(true);
    });

    it("fails on extra calls even if expected order is preserved", () => {
      const r = matchTrajectory(
        ["query_sites", "query_sites", "plan_route", "suggest_dining"],
        ["query_sites", "plan_route", "suggest_dining"],
        "exact"
      );
      expect(r.passed).toBe(false);
    });
  });

  describe("subset", () => {
    it("passes when all actual tools are in the expected set", () => {
      const r = matchTrajectory(
        ["suggest_dining"],
        ["suggest_dining"],
        "subset"
      );
      expect(r.passed).toBe(true);
    });

    it("passes when actual is a strict subset of expected", () => {
      const r = matchTrajectory(
        ["query_sites"],
        ["query_sites", "plan_route", "suggest_dining"],
        "subset"
      );
      expect(r.passed).toBe(true);
    });

    it("fails when actual contains unexpected tools", () => {
      const r = matchTrajectory(
        ["query_sites", "plan_route", "suggest_dining"],
        ["suggest_dining"],
        "subset"
      );
      expect(r.passed).toBe(false);
      expect(r.reason).toContain("query_sites");
    });

    it("catches thrashing — repeated unexpected tools", () => {
      const r = matchTrajectory(
        ["suggest_dining", "query_sites", "query_sites", "plan_route"],
        ["suggest_dining"],
        "subset"
      );
      expect(r.passed).toBe(false);
      expect(r.reason).toContain("unexpected");
    });
  });
});
