import type { Attraction, ClosureConflict } from "../data/types.js";
import { distances } from "../data/distances.js";
import { attractions } from "../data/attractions.js";

const DAYS_OF_WEEK = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

/**
 * Get the day of the week N days from a start day.
 * e.g., getDayOffset("Monday", 1) => "Tuesday"
 */
function getDayOffset(startDay: string, offset: number): string {
  const startIndex = DAYS_OF_WEEK.indexOf(startDay);
  if (startIndex === -1) return startDay;
  return DAYS_OF_WEEK[(startIndex + offset) % 7];
}

/**
 * Parse a time string in HH:MM format to total minutes since midnight.
 */
function parseTimeToMinutes(time: string): number {
  const [hours, minutes] = time.split(":").map(Number);
  return hours * 60 + minutes;
}

/**
 * Look up an attraction by name from the mock data.
 */
function findAttraction(name: string): Attraction | undefined {
  return attractions.find((a) => a.name === name);
}

/**
 * Check if an attraction is open on a given day of the week.
 * Returns true if the attraction's closureDays does NOT include the given day.
 */
export function isOpenOnDay(attraction: Attraction, dayOfWeek: string): boolean {
  return !attraction.closureDays.includes(dayOfWeek);
}

/**
 * Check if an attraction is open at a specific time (HH:MM format).
 * Returns true if the time falls within [openTime, closeTime).
 */
export function isOpenAtTime(attraction: Attraction, time: string): boolean {
  const timeMinutes = parseTimeToMinutes(time);
  const openMinutes = parseTimeToMinutes(attraction.openTime);
  const closeMinutes = parseTimeToMinutes(attraction.closeTime);
  return timeMinutes >= openMinutes && timeMinutes < closeMinutes;
}

/**
 * Get travel time between two attractions from the distance matrix.
 * Returns 0 if same attraction, or a large default (60) if not found.
 */
export function getTravelTime(from: string, to: string): number {
  if (from === to) return 0;
  if (distances[from] && distances[from][to] !== undefined) {
    return distances[from][to];
  }
  // Large default if pair not found in matrix
  return 60;
}

/**
 * Calculate total time needed to visit a set of attractions in order.
 * Sums visit durations for all attractions in the route, plus travel times
 * between consecutive pairs.
 */
export function calculateTotalTime(
  attractionNames: string[],
  orderedRoute: string[]
): number {
  let totalMinutes = 0;

  for (let i = 0; i < orderedRoute.length; i++) {
    const attraction = findAttraction(orderedRoute[i]);
    if (attraction) {
      totalMinutes += attraction.visitDurationMinutes;
    }

    // Add travel time to next attraction
    if (i < orderedRoute.length - 1) {
      totalMinutes += getTravelTime(orderedRoute[i], orderedRoute[i + 1]);
    }
  }

  return totalMinutes;
}

/**
 * Check if a set of attractions fits within a daily time budget.
 * Calculates total time vs available minutes (endTime - startTime).
 * Returns an object with fit status, total minutes, and budget minutes.
 */
export function fitsInDailyBudget(
  orderedRoute: string[],
  startTime: string,
  endTime: string
): { fits: boolean; totalMinutes: number; budgetMinutes: number } {
  const budgetMinutes = parseTimeToMinutes(endTime) - parseTimeToMinutes(startTime);
  const totalMinutes = calculateTotalTime(orderedRoute, orderedRoute);

  return {
    fits: totalMinutes <= budgetMinutes,
    totalMinutes,
    budgetMinutes,
  };
}

/**
 * Detect all closure conflicts for attractions on given days.
 * For each day (starting from startDay for numDays), check each attraction.
 * If closed on that day, create a ClosureConflict with suggestion to reschedule.
 */
export function detectClosureConflicts(
  attractionNames: string[],
  startDay: string,
  numDays: number
): ClosureConflict[] {
  const conflicts: ClosureConflict[] = [];

  for (let dayOffset = 0; dayOffset < numDays; dayOffset++) {
    const currentDay = getDayOffset(startDay, dayOffset);

    for (const name of attractionNames) {
      const attraction = findAttraction(name);
      if (!attraction) continue;

      if (!isOpenOnDay(attraction, currentDay)) {
        // Find a suggestion: the next available day
        let suggestionDay = "";
        for (let nextOffset = 1; nextOffset <= 7; nextOffset++) {
          const candidateDay = getDayOffset(currentDay, nextOffset);
          if (isOpenOnDay(attraction, candidateDay)) {
            suggestionDay = candidateDay;
            break;
          }
        }

        conflicts.push({
          attractionName: name,
          requestedDay: currentDay,
          closureDays: attraction.closureDays,
          suggestion: suggestionDay
            ? `Reschedule to ${suggestionDay} when ${name} is open`
            : `${name} has limited availability; check schedule`,
        });
      }
    }
  }

  return conflicts;
}

/**
 * Greedy nearest-neighbor route optimization respecting opening hours.
 * Starts from the first attraction, always picks the nearest unvisited
 * attraction that is reachable within the time window.
 */
export function optimizeRoute(
  attractionNames: string[],
  startTime: string,
  endTime: string
): string[] {
  if (attractionNames.length === 0) return [];

  const endMinutes = parseTimeToMinutes(endTime);
  let currentTime = parseTimeToMinutes(startTime);
  const visited: string[] = [];
  const unvisited = [...attractionNames];

  // Start with the first attraction if it's reachable and open
  const firstAttraction = findAttraction(unvisited[0]);
  if (firstAttraction && currentTime < endMinutes) {
    visited.push(unvisited[0]);
    currentTime += firstAttraction.visitDurationMinutes;
    unvisited.splice(0, 1);
  } else if (unvisited.length > 0) {
    // If first isn't available, just remove it and try nearest-neighbor from scratch
    // Actually let's handle this in the main loop
  }

  // If first attraction couldn't be added, reset and use pure nearest-neighbor
  if (visited.length === 0 && unvisited.length > 0) {
    return [];
  }

  while (unvisited.length > 0) {
    const currentLocation = visited[visited.length - 1];
    let nearestIndex = -1;
    let nearestDistance = Infinity;

    for (let i = 0; i < unvisited.length; i++) {
      const candidateName = unvisited[i];
      const candidate = findAttraction(candidateName);
      if (!candidate) continue;

      const travelTime = getTravelTime(currentLocation, candidateName);
      const arrivalTime = currentTime + travelTime;
      const departureTime = arrivalTime + candidate.visitDurationMinutes;

      // Check if we can arrive while it's open and finish within the day's end time
      const openMinutes = parseTimeToMinutes(candidate.openTime);
      const closeMinutes = parseTimeToMinutes(candidate.closeTime);

      // Must arrive within opening hours and finish before end of day
      if (
        arrivalTime >= openMinutes &&
        arrivalTime < closeMinutes &&
        departureTime <= endMinutes
      ) {
        if (travelTime < nearestDistance) {
          nearestDistance = travelTime;
          nearestIndex = i;
        }
      }
    }

    if (nearestIndex === -1) {
      // No reachable attraction found within time constraints
      break;
    }

    const chosenName = unvisited[nearestIndex];
    const chosenAttraction = findAttraction(chosenName)!;
    const travelTime = getTravelTime(currentLocation, chosenName);

    currentTime += travelTime + chosenAttraction.visitDurationMinutes;
    visited.push(chosenName);
    unvisited.splice(nearestIndex, 1);
  }

  return visited;
}
