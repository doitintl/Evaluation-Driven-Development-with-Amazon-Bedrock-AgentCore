// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

// Evaluation cases for the Luminara travel agent.
//
// Each case captures a real user request, the tool sequence the Coordinator
// SHOULD invoke, and the success criteria the response should satisfy.
//
// Trajectory matching modes (aligned with industry standards):
//   superset  — agent calls AT LEAST all expected tools (extras OK)
//               ≡ Strands any_order, AgentCore TrajectoryAnyOrderMatch, LangSmith Superset
//   in_order  — expected tools appear as subsequence (extras between them OK)
//               ≡ Strands in_order, AgentCore TrajectoryInOrderMatch
//   exact     — actual sequence equals expected exactly (no extras, no reordering)
//               ≡ Strands exact_match, AgentCore TrajectoryExactOrderMatch, LangSmith Strict
//   subset    — agent calls ONLY tools from expected set (no unexpected tools)
//               ≡ LangSmith Subset — catches thrashing/retry/hallucinated-tool patterns

export type TrajectoryMatchMode = "superset" | "in_order" | "exact" | "subset";

export interface Case {
  name: string;
  prompt: string;
  expected_trajectory: string[];
  trajectory_match: TrajectoryMatchMode;
  // Free-text rubric the LLM judge uses to score the response on a 0-1 scale.
  // Mention concrete facts the response MUST contain or constraints it MUST
  // respect. Avoid open-ended quality words like "good" or "comprehensive".
  rubric: string;
  // Optional: assertions are simple substring checks the harness runs
  // alongside the LLM judge. Each substring must appear in the response.
  must_contain?: string[];
  // Optional: substrings the response must NOT contain (closure-day violations).
  must_not_contain?: string[];
}

export const CASES: Case[] = [
  {
    name: "luminara_2day_history_monday",
    prompt:
      "Plan a 2-day Luminara trip arriving Monday focusing on history. I want to see the Grand Museum and the Royal Palace.",
    expected_trajectory: ["query_sites", "plan_route", "suggest_dining"],
    trajectory_match: "superset",
    rubric:
      "The Grand Museum closes on Monday and the Royal Palace closes on Tuesday. The itinerary MUST schedule the Grand Museum on day 2 (Tuesday) and the Royal Palace on day 1 (Monday), or it MUST explicitly state the closure conflict and offer an alternative day. The response MUST mention that the Royal Palace requires advance booking. The Coordinator MUST NOT schedule the Grand Museum on Monday day 1.",
    // No must_not_contain here, deliberately. It used to be
    //   ["Day 1: Monday", "Monday | Grand Museum"]
    // and it failed on every CORRECT answer: the agent renders its itinerary as
    // "=== Day 1: Monday ===", and day 1 really is Monday, so the first string
    // matched good output. The second could never match at all, because day
    // headings and attraction rows are on separate lines. A substring gate cannot
    // express "the Grand Museum appears under the Monday heading", so that
    // constraint is enforced by the rubric above instead, where the judge can see
    // the structure. Keep must_not_contain for strings that are unambiguously
    // wrong on their own.
  },
  {
    name: "luminara_weekend_attractions",
    prompt:
      "What attractions are open on weekends in Luminara? Pick 3 that span different categories.",
    expected_trajectory: ["query_sites"],
    trajectory_match: "superset",
    rubric:
      "The response MUST list at least 3 attractions that are open on Saturday and Sunday (no closure days, or closure days excluding both Saturday and Sunday). The response MUST identify the category for each attraction. The Night Market is acceptable since it is open Friday through Sunday evening. The Old Quarter Walking Tour is NOT acceptable for a Sunday recommendation since it closes on Sunday.",
  },
  {
    name: "luminara_advance_booking_aware",
    prompt:
      "Plan a 1-day itinerary that includes the Harbor Cruise and the Royal Palace.",
    expected_trajectory: ["query_sites", "plan_route", "suggest_dining"],
    trajectory_match: "superset",
    rubric:
      "Both Harbor Cruise and Royal Palace require advance booking. The response MUST mention this for BOTH attractions. The itinerary MUST place the Royal Palace on a day other than Tuesday. Time windows must respect each attraction's opening hours.",
    must_contain: ["advance booking"],
  },
  {
    name: "luminara_dining_focus",
    prompt:
      "Suggest where to have lunch on Day 2 if I'm visiting the Botanical Gardens that morning.",
    expected_trajectory: ["suggest_dining"],
    trajectory_match: "superset",
    rubric:
      "The response MUST recommend at least one restaurant suitable for lunch. The recommendation should be reasonably close to the Botanical Gardens (mention proximity if the dining tool returns it). The response should include the meal type (lunch) explicitly.",
  },
  {
    name: "luminara_3day_balanced",
    prompt:
      "Plan a 3-day Luminara trip starting Friday with a mix of history, nature, and food. Budget under $200 in attraction tickets.",
    expected_trajectory: ["query_sites", "plan_route", "suggest_dining"],
    trajectory_match: "in_order",
    rubric:
      "The response MUST schedule attractions across 3 days. Closure days MUST be respected (Grand Museum Mon, Royal Palace Tue, Old Quarter Sun, Luminara Art Gallery Mon+Wed). The total ticket cost should be under $200 OR the response should explicitly call out that the cost exceeds the budget. Dining suggestions MUST appear for at least one meal on at least one day.",
  },
  {
    name: "luminara_dining_only_scoped",
    prompt:
      "I'm already at the Skyline Tower. Where should I eat lunch nearby?",
    expected_trajectory: ["suggest_dining"],
    trajectory_match: "subset",
    rubric:
      "The response MUST recommend at least one restaurant for lunch near the Skyline Tower. The agent should NOT call query_sites or plan_route for this request — it is a simple dining lookup that does not require attraction data or route planning. Calling extra tools indicates the agent is over-planning.",
  },
];
