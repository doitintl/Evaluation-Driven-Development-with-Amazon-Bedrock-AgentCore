// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

import { Type, type Static } from "@sinclair/typebox";
import type { AgentTool, AgentToolResult } from "@mariozechner/pi-agent-core";
import type {
  RouteResult,
  Itinerary,
  DayPlan,
  ItineraryEntry,
  ClosureConflict,
  TimeOverflow,
  Attraction,
} from "../data/types.js";
import { attractions } from "../data/attractions.js";
import {
  isOpenOnDay,
  getTravelTime,
  detectClosureConflicts,
  fitsInDailyBudget,
} from "../utils/constraints.js";

const DAYS_OF_WEEK = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

const RoutePlanSchema = Type.Object({
  attractions: Type.Array(Type.String(), {
    description: "List of attraction names to visit",
  }),
  num_days: Type.Number({ description: "Number of days for the trip" }),
  start_day: Type.String({
    description: "Starting day of the week (e.g., 'Monday')",
  }),
  day_start_time: Type.Optional(
    Type.String({
      description: "Daily start time in HH:MM format (default: 09:00)",
    })
  ),
  day_end_time: Type.Optional(
    Type.String({
      description: "Daily end time in HH:MM format (default: 21:00)",
    })
  ),
});

type RoutePlanArgs = Static<typeof RoutePlanSchema>;

export function createRouteAgentTool(): AgentTool<typeof RoutePlanSchema, RouteResult> {
  return {
    name: "plan_route",
    label: "Route Planner",
    description:
      "Plan an optimized multi-day itinerary for given attractions. Handles constraint checking (closure days, opening hours, travel time, daily time budget) and returns a structured schedule or reports conflicts.",
    parameters: RoutePlanSchema,
    execute: async (toolCallId, args, signal, onUpdate) => {
      return planRoute(args);
    },
  };
}

// --- Helper functions ---

function getDayOffset(startDay: string, offset: number): string {
  const startIndex = DAYS_OF_WEEK.indexOf(startDay);
  if (startIndex === -1) return startDay;
  return DAYS_OF_WEEK[(startIndex + offset) % 7];
}

function parseTimeToMinutes(time: string): number {
  const [hours, minutes] = time.split(":").map(Number);
  return hours * 60 + minutes;
}

function minutesToTimeString(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}`;
}

function findAttraction(name: string): Attraction | undefined {
  return attractions.find((a) => a.name === name);
}

/**
 * Determine if an attraction has time restrictions that limit it to certain days.
 * Returns the list of days it IS open (empty array if open every day).
 */
function getAvailableDays(attraction: Attraction): string[] {
  if (attraction.closureDays.length === 0) return [];
  return DAYS_OF_WEEK.filter((day) => !attraction.closureDays.includes(day));
}

// --- Main route planning function ---

export function planRoute(args: RoutePlanArgs): AgentToolResult<RouteResult> {
  const {
    attractions: requestedAttractions,
    num_days,
    start_day,
    day_start_time = "09:00",
    day_end_time = "21:00",
  } = args;

  const dayStartMinutes = parseTimeToMinutes(day_start_time);
  const dayEndMinutes = parseTimeToMinutes(day_end_time);
  const dailyBudgetMinutes = dayEndMinutes - dayStartMinutes;

  // Validate requested attractions exist
  const validAttractions: Attraction[] = [];
  const unknownAttractions: string[] = [];
  for (const name of requestedAttractions) {
    const found = findAttraction(name);
    if (found) {
      validAttractions.push(found);
    } else {
      unknownAttractions.push(name);
    }
  }

  // Build day schedule: dayNumber -> dayOfWeek
  const daySchedule: { dayNumber: number; dayOfWeek: string }[] = [];
  for (let i = 0; i < num_days; i++) {
    daySchedule.push({
      dayNumber: i + 1,
      dayOfWeek: getDayOffset(start_day, i),
    });
  }

  // Step 1: Detect closure conflicts
  const allConflicts = detectClosureConflicts(
    validAttractions.map((a) => a.name),
    start_day,
    num_days
  );

  // Step 2: Assign time-restricted attractions first
  // Attractions with many closure days (like Night Market) get priority placement
  const timeRestricted = validAttractions
    .filter((a) => a.closureDays.length >= 3)
    .sort((a, b) => b.closureDays.length - a.closureDays.length); // most restricted first

  const unrestricted = validAttractions.filter(
    (a) => a.closureDays.length < 3
  );

  // Track which attractions are assigned to which day
  const dayAssignments: Map<number, string[]> = new Map();
  for (let i = 0; i < num_days; i++) {
    dayAssignments.set(i, []);
  }
  const assigned = new Set<string>();
  const adjustments: string[] = [];

  // Assign time-restricted attractions to their available days
  for (const attraction of timeRestricted) {
    const availableDays = getAvailableDays(attraction);
    let placed = false;

    for (let dayIdx = 0; dayIdx < num_days; dayIdx++) {
      const dayOfWeek = daySchedule[dayIdx].dayOfWeek;
      if (availableDays.includes(dayOfWeek)) {
        dayAssignments.get(dayIdx)!.push(attraction.name);
        assigned.add(attraction.name);
        placed = true;

        // Check if this required rescheduling from a different day
        if (allConflicts.some((c) => c.attractionName === attraction.name)) {
          adjustments.push(
            `${attraction.name} scheduled on ${dayOfWeek} (Day ${dayIdx + 1}) — only open on ${availableDays.join(", ")}`
          );
        }
        break;
      }
    }

    if (!placed) {
      adjustments.push(
        `${attraction.name} could not be scheduled — not open on any of the trip days (${daySchedule.map((d) => d.dayOfWeek).join(", ")})`
      );
    }
  }

  // Step 3: Fill days greedily with unrestricted attractions
  // For each day, pick nearest unvisited attraction that is open and fits in time budget
  for (let dayIdx = 0; dayIdx < num_days; dayIdx++) {
    const dayOfWeek = daySchedule[dayIdx].dayOfWeek;
    const currentDayAttractions = dayAssignments.get(dayIdx)!;

    // Filter unrestricted attractions that are open on this day and not yet assigned
    const candidates = unrestricted.filter(
      (a) => !assigned.has(a.name) && isOpenOnDay(a, dayOfWeek)
    );

    // Calculate remaining time budget for this day after pre-assigned attractions
    let usedMinutes = 0;
    for (const name of currentDayAttractions) {
      const attr = findAttraction(name)!;
      usedMinutes += attr.visitDurationMinutes;
      // Add travel time from previous attraction in the day
      if (currentDayAttractions.indexOf(name) > 0) {
        const prevName =
          currentDayAttractions[currentDayAttractions.indexOf(name) - 1];
        usedMinutes += getTravelTime(prevName, name);
      }
    }

    // Greedy nearest-neighbor fill
    while (candidates.length > 0) {
      const lastAttraction =
        currentDayAttractions.length > 0
          ? currentDayAttractions[currentDayAttractions.length - 1]
          : null;

      let bestIdx = -1;
      let bestTravelTime = Infinity;

      for (let i = 0; i < candidates.length; i++) {
        const candidate = candidates[i];
        const travelTime = lastAttraction
          ? getTravelTime(lastAttraction, candidate.name)
          : 0;
        const totalNeeded = travelTime + candidate.visitDurationMinutes;

        // Check if candidate fits in remaining daily budget
        if (usedMinutes + totalNeeded <= dailyBudgetMinutes) {
          // Check if we can arrive within the attraction's opening hours
          const arrivalMinutes = dayStartMinutes + usedMinutes + travelTime;
          const openMinutes = parseTimeToMinutes(candidate.openTime);
          const closeMinutes = parseTimeToMinutes(candidate.closeTime);

          if (
            arrivalMinutes >= openMinutes &&
            arrivalMinutes < closeMinutes &&
            arrivalMinutes + candidate.visitDurationMinutes <= closeMinutes
          ) {
            if (travelTime < bestTravelTime) {
              bestTravelTime = travelTime;
              bestIdx = i;
            }
          }
        }
      }

      if (bestIdx === -1) break; // No more candidates fit

      const chosen = candidates[bestIdx];
      const travelTime = lastAttraction
        ? getTravelTime(lastAttraction, chosen.name)
        : 0;

      currentDayAttractions.push(chosen.name);
      assigned.add(chosen.name);
      usedMinutes += travelTime + chosen.visitDurationMinutes;
      candidates.splice(bestIdx, 1);
    }
  }

  // Handle attractions that couldn't be assigned due to closure conflicts
  // Try to reschedule conflicting unrestricted attractions to another day
  for (const attraction of unrestricted) {
    if (assigned.has(attraction.name)) continue;

    // This attraction wasn't placed — find any available day
    let placed = false;
    for (let dayIdx = 0; dayIdx < num_days; dayIdx++) {
      const dayOfWeek = daySchedule[dayIdx].dayOfWeek;
      if (isOpenOnDay(attraction, dayOfWeek)) {
        // Check if it fits in the day's remaining budget
        const currentDayAttractions = dayAssignments.get(dayIdx)!;
        let usedMinutes = 0;
        for (let i = 0; i < currentDayAttractions.length; i++) {
          const attr = findAttraction(currentDayAttractions[i])!;
          usedMinutes += attr.visitDurationMinutes;
          if (i > 0) {
            usedMinutes += getTravelTime(
              currentDayAttractions[i - 1],
              currentDayAttractions[i]
            );
          }
        }

        const lastInDay =
          currentDayAttractions.length > 0
            ? currentDayAttractions[currentDayAttractions.length - 1]
            : null;
        const travelTime = lastInDay
          ? getTravelTime(lastInDay, attraction.name)
          : 0;
        const totalNeeded = travelTime + attraction.visitDurationMinutes;

        if (usedMinutes + totalNeeded <= dailyBudgetMinutes) {
          currentDayAttractions.push(attraction.name);
          assigned.add(attraction.name);
          placed = true;

          const conflict = allConflicts.find(
            (c) => c.attractionName === attraction.name
          );
          if (conflict) {
            adjustments.push(
              `${attraction.name} rescheduled from ${conflict.requestedDay} to ${dayOfWeek} (Day ${dayIdx + 1}) — closed on ${conflict.requestedDay}`
            );
          }
          break;
        }
      }
    }

    if (!placed) {
      adjustments.push(
        `${attraction.name} could not fit within the ${num_days}-day schedule`
      );
    }
  }

  // Step 4: Check for overflow (unassigned attractions)
  const unassigned = validAttractions.filter((a) => !assigned.has(a.name));
  let overflow: TimeOverflow | undefined;

  if (unassigned.length > 0) {
    // Calculate total time requested vs available
    const totalRequestedMinutes = validAttractions.reduce(
      (sum, a) => sum + a.visitDurationMinutes,
      0
    );
    const totalAvailableMinutes = num_days * dailyBudgetMinutes;

    overflow = {
      requestedMinutes: totalRequestedMinutes,
      availableMinutes: totalAvailableMinutes,
      suggestion: `Consider splitting across ${Math.ceil(totalRequestedMinutes / dailyBudgetMinutes)} days instead of ${num_days}`,
    };
  }

  // Step 5: Build the itinerary with proper ItineraryEntry objects
  const days: DayPlan[] = [];
  let totalCost = 0;
  let totalAttractionsVisited = 0;

  for (let dayIdx = 0; dayIdx < num_days; dayIdx++) {
    const dayOfWeek = daySchedule[dayIdx].dayOfWeek;
    const dayAttractions = dayAssignments.get(dayIdx)!;
    const entries: ItineraryEntry[] = [];
    let currentTimeMinutes = dayStartMinutes;

    for (let i = 0; i < dayAttractions.length; i++) {
      const attractionName = dayAttractions[i];
      const attraction = findAttraction(attractionName)!;

      // Add travel entry if not the first attraction
      if (i > 0) {
        const prevName = dayAttractions[i - 1];
        const travelTime = getTravelTime(prevName, attractionName);
        if (travelTime > 0) {
          const travelStart = minutesToTimeString(currentTimeMinutes);
          currentTimeMinutes += travelTime;
          const travelEnd = minutesToTimeString(currentTimeMinutes);

          entries.push({
            startTime: travelStart,
            endTime: travelEnd,
            name: `Travel to ${attractionName}`,
            activityType: "travel",
            durationMinutes: travelTime,
          });
        }
      }

      // Wait for attraction to open if arriving before opening time
      const attractionOpenMinutes = parseTimeToMinutes(attraction.openTime);
      if (currentTimeMinutes < attractionOpenMinutes) {
        currentTimeMinutes = attractionOpenMinutes;
      }

      // Add visit entry
      const visitStart = minutesToTimeString(currentTimeMinutes);
      currentTimeMinutes += attraction.visitDurationMinutes;
      const visitEnd = minutesToTimeString(currentTimeMinutes);

      const notes: string[] = [];
      if (attraction.advanceBookingRequired) {
        notes.push("Advance booking required");
      }
      const conflict = allConflicts.find(
        (c) => c.attractionName === attractionName
      );
      if (conflict) {
        notes.push(
          `Rescheduled — closed on ${conflict.requestedDay}`
        );
      }

      entries.push({
        startTime: visitStart,
        endTime: visitEnd,
        name: attractionName,
        activityType: "visit",
        durationMinutes: attraction.visitDurationMinutes,
        ...(notes.length > 0 ? { notes: notes.join("; ") } : {}),
      });

      totalCost += attraction.ticketPrice;
      totalAttractionsVisited++;
    }

    days.push({
      dayNumber: dayIdx + 1,
      dayOfWeek,
      entries,
    });
  }

  // Add unknown attraction notes
  if (unknownAttractions.length > 0) {
    adjustments.push(
      `Unknown attractions (not found in data): ${unknownAttractions.join(", ")}`
    );
  }

  const itinerary: Itinerary = {
    days,
    totalCost,
    totalAttractions: totalAttractionsVisited,
    adjustments,
  };

  // Determine success: all requested valid attractions were scheduled
  const success = unassigned.length === 0 && unknownAttractions.length === 0;

  const result: RouteResult = {
    success,
    itinerary,
    ...(allConflicts.length > 0 ? { conflicts: allConflicts } : {}),
    ...(overflow ? { overflow } : {}),
    ...(adjustments.length > 0 ? { adjustments } : {}),
  };

  // Build text content for the LLM
  const lines: string[] = [];

  if (success) {
    lines.push(` Successfully planned a ${num_days}-day itinerary with ${totalAttractionsVisited} attractions.`);
  } else {
    lines.push(`⚠️ Itinerary planned with adjustments needed.`);
  }

  lines.push("");

  for (const day of days) {
    lines.push(`=== Day ${day.dayNumber}: ${day.dayOfWeek} ===`);
    for (const entry of day.entries) {
      const noteStr = entry.notes ? ` (${entry.notes})` : "";
      lines.push(
        `  ${entry.startTime}–${entry.endTime} | ${entry.name} [${entry.activityType}] (${entry.durationMinutes} min)${noteStr}`
      );
    }
    lines.push("");
  }

  if (adjustments.length > 0) {
    lines.push("Adjustments:");
    for (const adj of adjustments) {
      lines.push(`  - ${adj}`);
    }
    lines.push("");
  }

  if (overflow) {
    lines.push(` Time Overflow: Requested ${overflow.requestedMinutes} min, available ${overflow.availableMinutes} min.`);
    lines.push(`  Suggestion: ${overflow.suggestion}`);
    lines.push("");
  }

  if (allConflicts.length > 0) {
    lines.push("Closure Conflicts Detected:");
    for (const conflict of allConflicts) {
      lines.push(
        `  - ${conflict.attractionName}: closed on ${conflict.requestedDay} (${conflict.suggestion})`
      );
    }
  }

  lines.push(`\nEstimated total cost: $${totalCost}`);

  return {
    content: [{ type: "text", text: lines.join("\n") }],
    details: result,
  };
}
