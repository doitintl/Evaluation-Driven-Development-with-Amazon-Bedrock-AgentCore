import type { Itinerary, DayPlan, ItineraryEntry } from "../data/types.js";

/**
 * Format entries within a day in chronological order by start time.
 */
function sortEntries(entries: ItineraryEntry[]): ItineraryEntry[] {
  return [...entries].sort((a, b) => a.startTime.localeCompare(b.startTime));
}

/**
 * Format a single day's plan with header and chronological entries.
 */
export function formatDayPlan(day: DayPlan, dayNumber: number): string {
  const lines: string[] = [];

  lines.push(`=== Day ${dayNumber}: ${day.dayOfWeek} ===`);

  const sorted = sortEntries(day.entries);
  for (const entry of sorted) {
    let line = `  ${entry.startTime}-${entry.endTime} | ${entry.name} [${entry.activityType}] (${entry.durationMinutes} min)`;
    if (entry.notes) {
      line += ` — ${entry.notes}`;
    }
    lines.push(line);
  }

  return lines.join("\n");
}

/**
 * Generate the summary section for an itinerary.
 */
export function formatSummary(itinerary: Itinerary): string {
  const lines: string[] = [];

  lines.push("--- Summary ---");
  lines.push(`Total attractions: ${itinerary.totalAttractions}`);
  lines.push(`Total days: ${itinerary.days.length}`);
  lines.push(`Estimated total cost: $${itinerary.totalCost}`);

  if (itinerary.adjustments.length > 0) {
    lines.push("Schedule Adjustments:");
    for (const adjustment of itinerary.adjustments) {
      lines.push(`  • ${adjustment}`);
    }
  }

  return lines.join("\n");
}

/**
 * Format a structured itinerary into the standard text output.
 * Includes day plans followed by a summary section.
 */
export function formatItinerary(itinerary: Itinerary): string {
  const parts: string[] = [];

  for (let i = 0; i < itinerary.days.length; i++) {
    parts.push(formatDayPlan(itinerary.days[i], i + 1));
  }

  parts.push(formatSummary(itinerary));

  return parts.join("\n\n");
}
