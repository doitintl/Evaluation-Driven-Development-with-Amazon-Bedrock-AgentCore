// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

import { describe, it, expect, beforeAll } from "vitest";
import { createCoordinatorAgent } from "../../src/coordinator.js";
import { loadConfig } from "../../src/utils/config.js";
import { attractions } from "../../src/data/attractions.js";

/**
 * E2E: Itinerary Planning
 *
 * Validates Requirements: 1.8, 10.6, 10.7
 *
 * This test suite invokes the full Coordinator Agent with a real Bedrock call
 * and validates the structured itinerary output. Skippable via SKIP_E2E=true.
 */

const SKIP = process.env.SKIP_E2E === "true";

// Attractions closed on Monday (from mock data)
const MONDAY_CLOSED_ATTRACTIONS = attractions
  .filter((a) => a.closureDays.includes("Monday"))
  .map((a) => a.name);

// Maximum daily activity window in minutes (09:00 to 21:00 = 12 hours)
const MAX_DAILY_MINUTES = 720;

/**
 * Extract the last assistant text response from agent state messages.
 */
function getLastAssistantText(agent: { state: { messages: any[] } }): string {
  const messages = agent.state.messages;
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];
    if (msg && "role" in msg && msg.role === "assistant") {
      const textParts = msg.content
        .filter((c: any): c is { type: "text"; text: string } => c.type === "text")
        .map((c: any) => c.text);
      return textParts.join("");
    }
  }
  return "";
}

/**
 * Extract the Day 1 section from itinerary text.
 * Looks for content between Day 1 header and Day 2 header.
 */
function extractDay1Section(text: string): string {
  // Match patterns like "=== Day 1" or "Day 1:" or "**Day 1"
  const day1Match = text.match(/(?:={2,}\s*)?Day\s*1[:\s]/i);
  const day2Match = text.match(/(?:={2,}\s*)?Day\s*2[:\s]/i);

  if (!day1Match) return "";

  const startIdx = day1Match.index!;
  const endIdx = day2Match ? day2Match.index! : text.length;

  return text.substring(startIdx, endIdx);
}

/**
 * Parse time durations from itinerary text.
 * Looks for time ranges like "09:00–11:00" or "09:00-11:00" and
 * calculates total scheduled minutes per day.
 */
function parseDailyMinutes(text: string): number[] {
  const dailyMinutes: number[] = [];

  // Split by day headers
  const dayPattern = /(?:={2,}\s*)?Day\s*\d+/gi;
  const daySections = text.split(dayPattern).filter((s) => s.trim().length > 0);

  for (const section of daySections) {
    // Find all time ranges like "09:00–11:00" or "09:00-11:00"
    const timeRangePattern = /(\d{1,2}):(\d{2})\s*[–\-—]\s*(\d{1,2}):(\d{2})/g;
    let totalMinutes = 0;
    let match: RegExpExecArray | null;

    while ((match = timeRangePattern.exec(section)) !== null) {
      const startHour = parseInt(match[1], 10);
      const startMin = parseInt(match[2], 10);
      const endHour = parseInt(match[3], 10);
      const endMin = parseInt(match[4], 10);

      const startTotal = startHour * 60 + startMin;
      const endTotal = endHour * 60 + endMin;
      const duration = endTotal - startTotal;

      if (duration > 0) {
        totalMinutes += duration;
      }
    }

    if (totalMinutes > 0) {
      dailyMinutes.push(totalMinutes);
    }
  }

  return dailyMinutes;
}

describe.skipIf(SKIP)("E2E: Itinerary Planning", () => {
  let responseText: string;

  beforeAll(async () => {
    let config: ReturnType<typeof loadConfig>;
    try {
      config = loadConfig();
    } catch {
      throw new Error(
        "Failed to load config. Ensure AWS_REGION is set. " +
          "Set SKIP_E2E=true to skip E2E tests without AWS credentials."
      );
    }

    const agent = createCoordinatorAgent(config);

    try {
      await agent.prompt(
        "Plan a 2-day trip focusing on history and food, arriving Monday"
      );
      responseText = getLastAssistantText(agent);
    } catch (error: any) {
      const msg = error?.message?.toLowerCase() ?? "";
      if (
        msg.includes("credential") ||
        msg.includes("expired") ||
        msg.includes("accessdenied") ||
        msg.includes("security token")
      ) {
        throw new Error(
          "AWS credential error: " +
            error.message +
            ". Set SKIP_E2E=true to skip E2E tests."
        );
      }
      throw error;
    }

    if (!responseText) {
      // Check if agent captured an error in its state
      const errorMsg = agent.state.errorMessage;
      throw new Error(
        "Agent returned empty response." +
          (errorMsg ? ` Agent error: ${errorMsg}` : "") +
          " Ensure valid AWS credentials are configured or set SKIP_E2E=true."
      );
    }
  }, 120_000); // 2 minute timeout for Bedrock call

  it("produces a response with structured day headers", () => {
    expect(responseText).toBeTruthy();

    // Verify response contains Day 1 and Day 2 indicators
    const hasDay1 = /Day\s*1/i.test(responseText);
    const hasDay2 = /Day\s*2/i.test(responseText);

    expect(hasDay1).toBe(true);
    expect(hasDay2).toBe(true);
  });

  it("does not schedule Monday-closed attractions on Day 1 (Monday)", () => {
    const day1Section = extractDay1Section(responseText);

    // Day 1 is Monday — verify no Monday-closed attractions appear
    for (const attractionName of MONDAY_CLOSED_ATTRACTIONS) {
      expect(
        day1Section,
        `Monday-closed attraction "${attractionName}" should not appear in Day 1 (Monday) section`
      ).not.toContain(attractionName);
    }
  });

  it("does not exceed maximum daily activity window (12 hours)", () => {
    const dailyMinutes = parseDailyMinutes(responseText);

    // If we can parse time ranges, validate they don't exceed 12 hours
    // The agent may not always output parseable time ranges, so only assert
    // when we successfully extract durations
    if (dailyMinutes.length > 0) {
      for (let i = 0; i < dailyMinutes.length; i++) {
        expect(
          dailyMinutes[i],
          `Day ${i + 1} total scheduled time (${dailyMinutes[i]} min) exceeds maximum ${MAX_DAILY_MINUTES} min`
        ).toBeLessThanOrEqual(MAX_DAILY_MINUTES);
      }
    }
  });
});
