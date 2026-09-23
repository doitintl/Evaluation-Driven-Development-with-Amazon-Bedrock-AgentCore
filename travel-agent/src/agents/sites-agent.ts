// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

import { Type, type Static } from "@sinclair/typebox";
import type { AgentTool, AgentToolResult } from "@mariozechner/pi-agent-core";
import { attractions } from "../data/attractions.js";
import type { Attraction } from "../data/types.js";

const SitesQuerySchema = Type.Object({
  query: Type.String({
    description:
      "Search query for attractions (name, category, or 'all')",
  }),
  day_of_week: Type.Optional(
    Type.String({
      description:
        "Day to check availability (e.g., 'Monday'). Every match is still returned; the ones closed that day are flagged as unavailable.",
    })
  ),
});

type SitesQuery = Static<typeof SitesQuerySchema>;

export function createSitesAgentTool(): AgentTool<typeof SitesQuerySchema, Attraction[]> {
  return {
    name: "query_sites",
    label: "Query Sites",
    description:
      "Query information about attractions in the city including opening hours, closure days, visit duration, ticket prices, and booking requirements. Use this to look up attraction details before planning routes.",
    parameters: SitesQuerySchema,
    execute: async (toolCallId, args, signal, onUpdate) => {
      return querySites(args);
    },
  };
}

export function querySites(args: SitesQuery): AgentToolResult<Attraction[]> {
  const { query, day_of_week } = args;

  let filtered: Attraction[];

  if (query.toLowerCase() === "all") {
    filtered = [...attractions];
  } else {
    const lowerQuery = query.toLowerCase();
    filtered = attractions.filter(
      (a) =>
        a.name.toLowerCase().includes(lowerQuery) ||
        a.category.toLowerCase() === lowerQuery
    );
  }

  // day_of_week asks "is this open that day?", so answer it in place. Dropping the
  // closed attractions here would delete the very closure the route planner needs:
  // plan_route already detects a closure conflict and reschedules around it, and the
  // caller would instead be told the attraction does not exist.

  // Build text content with booking advisories
  const lines: string[] = [];

  if (filtered.length === 0) {
    lines.push(`No attractions found matching "${query}".`);
  } else {
    for (const attraction of filtered) {
      lines.push(`**${attraction.name}** (${attraction.category})`);
      lines.push(`  ${attraction.description}`);
      lines.push(
        `  Hours: ${attraction.openTime}–${attraction.closeTime}`
      );
      if (attraction.closureDays.length > 0) {
        lines.push(`  Closed: ${attraction.closureDays.join(", ")}`);
      }
      if (day_of_week && attraction.closureDays.includes(day_of_week)) {
        lines.push(
          `  ⚠️ NOT AVAILABLE on ${day_of_week}. Schedule it on another day instead.`
        );
      }
      lines.push(`  Visit duration: ${attraction.visitDurationMinutes} minutes`);
      lines.push(`  Ticket price: $${attraction.ticketPrice}`);

      if (attraction.advanceBookingRequired) {
        lines.push(
          `  ⚠️ BOOKING ADVISORY: Advance booking is required for ${attraction.name}. Reserve tickets before your visit.`
        );
      }

      lines.push("");
    }
  }

  return {
    content: [{ type: "text", text: lines.join("\n") }],
    details: filtered,
  };
}
