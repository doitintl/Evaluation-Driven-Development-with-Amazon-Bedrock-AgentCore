# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Route planner specialist tool — port of agents/route-agent.ts.

Exports a single ``plan_route`` Strands tool. The closure-detection,
priority-placement (time-restricted attractions first), and greedy
nearest-neighbor scheduling logic mirrors the TypeScript original line-for-line.
This determinism is required by Module 4 (model-swap pedagogy).
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional

from strands import tool

from ..data.attractions import attractions
from ..data.types import (
    Attraction,
    ClosureConflict,
    DayPlan,
    Itinerary,
    ItineraryEntry,
    RouteResult,
    TimeOverflow,
)
from ..utils.constraints import (
    DAYS_OF_WEEK,
    detect_closure_conflicts,
    find_attraction,
    get_day_offset,
    get_travel_time,
    is_open_on_day,
    parse_time_to_minutes,
)


def _minutes_to_time_string(minutes: int) -> str:
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


def _get_available_days(attraction: Attraction) -> List[str]:
    """Return the list of days the attraction IS open. Empty if open every day."""
    if not attraction.closure_days:
        return []
    return [d for d in DAYS_OF_WEEK if d not in attraction.closure_days]


@tool
def plan_route(
    attractions_to_visit: List[str],
    num_days: int,
    start_day: str,
    day_start_time: str = "09:00",
    day_end_time: str = "21:00",
) -> str:
    """Plan an optimized multi-day itinerary for given attractions. Handles constraint checking (closure days, opening hours, travel time, daily time budget) and returns a structured schedule or reports conflicts.

    Args:
        attractions_to_visit: List of attraction names to visit.
        num_days: Number of days for the trip.
        start_day: Starting day of the week (e.g., 'Monday').
        day_start_time: Daily start time in HH:MM format (default 09:00).
        day_end_time: Daily end time in HH:MM format (default 21:00).

    Returns:
        Formatted multi-line itinerary text including a per-day schedule,
        adjustments, conflicts, and an estimated cost.
    """
    day_start_minutes = parse_time_to_minutes(day_start_time)
    day_end_minutes = parse_time_to_minutes(day_end_time)
    daily_budget_minutes = day_end_minutes - day_start_minutes

    # Validate requested attractions exist
    valid_attractions: List[Attraction] = []
    unknown_attractions: List[str] = []
    for name in attractions_to_visit:
        found = find_attraction(name)
        if found is not None:
            valid_attractions.append(found)
        else:
            unknown_attractions.append(name)

    # Build day schedule: dayNumber -> dayOfWeek
    day_schedule: List[Dict[str, object]] = []
    for i in range(num_days):
        day_schedule.append(
            {"dayNumber": i + 1, "dayOfWeek": get_day_offset(start_day, i)}
        )

    # Step 1: Detect closure conflicts
    all_conflicts: List[ClosureConflict] = detect_closure_conflicts(
        [a.name for a in valid_attractions], start_day, num_days
    )

    # Step 2: Assign time-restricted attractions first
    # Attractions with many closure days (like Night Market) get priority placement
    time_restricted = sorted(
        [a for a in valid_attractions if len(a.closure_days) >= 3],
        key=lambda a: len(a.closure_days),
        reverse=True,
    )
    unrestricted = [a for a in valid_attractions if len(a.closure_days) < 3]

    # Track which attractions are assigned to which day
    day_assignments: Dict[int, List[str]] = {i: [] for i in range(num_days)}
    assigned: set[str] = set()
    adjustments: List[str] = []

    # Assign time-restricted attractions to their available days
    for attraction in time_restricted:
        available_days = _get_available_days(attraction)
        placed = False

        for day_idx in range(num_days):
            day_of_week = day_schedule[day_idx]["dayOfWeek"]
            if day_of_week in available_days:
                day_assignments[day_idx].append(attraction.name)
                assigned.add(attraction.name)
                placed = True

                # Check if this required rescheduling from a different day
                if any(c.attraction_name == attraction.name for c in all_conflicts):
                    adjustments.append(
                        f"{attraction.name} scheduled on {day_of_week} "
                        f"(Day {day_idx + 1}) — only open on "
                        f"{', '.join(available_days)}"
                    )
                break

        if not placed:
            day_list = ", ".join(str(d["dayOfWeek"]) for d in day_schedule)
            adjustments.append(
                f"{attraction.name} could not be scheduled — not open on any "
                f"of the trip days ({day_list})"
            )

    # Step 3: Fill days greedily with unrestricted attractions
    # For each day, pick nearest unvisited attraction that is open and fits in time budget
    for day_idx in range(num_days):
        day_of_week = str(day_schedule[day_idx]["dayOfWeek"])
        current_day_attractions = day_assignments[day_idx]

        # Filter unrestricted attractions that are open on this day and not yet assigned
        candidates = [
            a
            for a in unrestricted
            if a.name not in assigned and is_open_on_day(a, day_of_week)
        ]

        # Calculate remaining time budget for this day after pre-assigned attractions
        used_minutes = 0
        for idx, name in enumerate(current_day_attractions):
            attr = find_attraction(name)
            if attr is None:
                continue
            used_minutes += attr.visit_duration_minutes
            # Add travel time from previous attraction in the day
            if idx > 0:
                prev_name = current_day_attractions[idx - 1]
                used_minutes += get_travel_time(prev_name, name)

        # Greedy nearest-neighbor fill
        while candidates:
            last_attraction = (
                current_day_attractions[-1] if current_day_attractions else None
            )

            best_idx = -1
            best_travel_time = math.inf

            for i, candidate in enumerate(candidates):
                travel_time = (
                    get_travel_time(last_attraction, candidate.name)
                    if last_attraction
                    else 0
                )
                total_needed = travel_time + candidate.visit_duration_minutes

                # Check if candidate fits in remaining daily budget
                if used_minutes + total_needed <= daily_budget_minutes:
                    # Check if we can arrive within the attraction's opening hours
                    arrival_minutes = day_start_minutes + used_minutes + travel_time
                    open_minutes = parse_time_to_minutes(candidate.open_time)
                    close_minutes = parse_time_to_minutes(candidate.close_time)

                    if (
                        arrival_minutes >= open_minutes
                        and arrival_minutes < close_minutes
                        and arrival_minutes + candidate.visit_duration_minutes
                        <= close_minutes
                    ):
                        if travel_time < best_travel_time:
                            best_travel_time = travel_time
                            best_idx = i

            if best_idx == -1:
                break  # No more candidates fit

            chosen = candidates[best_idx]
            travel_time = (
                get_travel_time(last_attraction, chosen.name) if last_attraction else 0
            )

            current_day_attractions.append(chosen.name)
            assigned.add(chosen.name)
            used_minutes += travel_time + chosen.visit_duration_minutes
            candidates.pop(best_idx)

    # Handle attractions that couldn't be assigned due to closure conflicts
    # Try to reschedule conflicting unrestricted attractions to another day
    for attraction in unrestricted:
        if attraction.name in assigned:
            continue

        # This attraction wasn't placed — find any available day
        placed = False
        for day_idx in range(num_days):
            day_of_week = str(day_schedule[day_idx]["dayOfWeek"])
            if not is_open_on_day(attraction, day_of_week):
                continue

            # Check if it fits in the day's remaining budget
            current_day_attractions = day_assignments[day_idx]
            used_minutes = 0
            for i, name in enumerate(current_day_attractions):
                attr = find_attraction(name)
                if attr is None:
                    continue
                used_minutes += attr.visit_duration_minutes
                if i > 0:
                    used_minutes += get_travel_time(
                        current_day_attractions[i - 1],
                        current_day_attractions[i],
                    )

            last_in_day = (
                current_day_attractions[-1] if current_day_attractions else None
            )
            travel_time = (
                get_travel_time(last_in_day, attraction.name) if last_in_day else 0
            )
            total_needed = travel_time + attraction.visit_duration_minutes

            if used_minutes + total_needed <= daily_budget_minutes:
                current_day_attractions.append(attraction.name)
                assigned.add(attraction.name)
                placed = True

                conflict = next(
                    (c for c in all_conflicts if c.attraction_name == attraction.name),
                    None,
                )
                if conflict is not None:
                    adjustments.append(
                        f"{attraction.name} rescheduled from "
                        f"{conflict.requested_day} to {day_of_week} "
                        f"(Day {day_idx + 1}) — closed on "
                        f"{conflict.requested_day}"
                    )
                break

        if not placed:
            adjustments.append(
                f"{attraction.name} could not fit within the {num_days}-day schedule"
            )

    # Step 4: Check for overflow (unassigned attractions)
    unassigned = [a for a in valid_attractions if a.name not in assigned]
    overflow: Optional[TimeOverflow] = None

    if unassigned:
        total_requested_minutes = sum(a.visit_duration_minutes for a in valid_attractions)
        total_available_minutes = num_days * daily_budget_minutes
        overflow = TimeOverflow(
            requested_minutes=total_requested_minutes,
            available_minutes=total_available_minutes,
            suggestion=(
                f"Consider splitting across "
                f"{math.ceil(total_requested_minutes / daily_budget_minutes)} "
                f"days instead of {num_days}"
            ),
        )

    # Step 5: Build the itinerary with proper ItineraryEntry objects
    days: List[DayPlan] = []
    total_cost = 0
    total_attractions_visited = 0

    for day_idx in range(num_days):
        day_of_week = str(day_schedule[day_idx]["dayOfWeek"])
        day_attractions = day_assignments[day_idx]
        entries: List[ItineraryEntry] = []
        current_time_minutes = day_start_minutes

        for i, attraction_name in enumerate(day_attractions):
            attraction = find_attraction(attraction_name)
            if attraction is None:
                continue

            # Add travel entry if not the first attraction
            if i > 0:
                prev_name = day_attractions[i - 1]
                travel_time = get_travel_time(prev_name, attraction_name)
                if travel_time > 0:
                    travel_start = _minutes_to_time_string(current_time_minutes)
                    current_time_minutes += travel_time
                    travel_end = _minutes_to_time_string(current_time_minutes)
                    entries.append(
                        ItineraryEntry(
                            start_time=travel_start,
                            end_time=travel_end,
                            name=f"Travel to {attraction_name}",
                            activity_type="travel",
                            duration_minutes=travel_time,
                        )
                    )

            # Wait for attraction to open if arriving before opening time
            attraction_open_minutes = parse_time_to_minutes(attraction.open_time)
            if current_time_minutes < attraction_open_minutes:
                current_time_minutes = attraction_open_minutes

            # Add visit entry
            visit_start = _minutes_to_time_string(current_time_minutes)
            current_time_minutes += attraction.visit_duration_minutes
            visit_end = _minutes_to_time_string(current_time_minutes)

            notes_parts: List[str] = []
            if attraction.advance_booking_required:
                notes_parts.append("Advance booking required")
            conflict = next(
                (c for c in all_conflicts if c.attraction_name == attraction_name),
                None,
            )
            if conflict is not None:
                notes_parts.append(f"Rescheduled — closed on {conflict.requested_day}")

            entries.append(
                ItineraryEntry(
                    start_time=visit_start,
                    end_time=visit_end,
                    name=attraction_name,
                    activity_type="visit",
                    duration_minutes=attraction.visit_duration_minutes,
                    notes="; ".join(notes_parts) if notes_parts else None,
                )
            )

            total_cost += attraction.ticket_price
            total_attractions_visited += 1

        days.append(
            DayPlan(day_number=day_idx + 1, day_of_week=day_of_week, entries=entries)
        )

    # Add unknown attraction notes
    if unknown_attractions:
        adjustments.append(
            f"Unknown attractions (not found in data): {', '.join(unknown_attractions)}"
        )

    itinerary = Itinerary(
        days=days,
        total_cost=total_cost,
        total_attractions=total_attractions_visited,
        adjustments=adjustments,
    )

    # Determine success: all requested valid attractions were scheduled
    success = not unassigned and not unknown_attractions

    result = RouteResult(
        success=success,
        itinerary=itinerary,
        conflicts=all_conflicts if all_conflicts else None,
        overflow=overflow,
        adjustments=adjustments if adjustments else None,
    )

    # Build text content for the LLM
    lines: List[str] = []

    if success:
        lines.append(
            f"Successfully planned a {num_days}-day itinerary with "
            f"{total_attractions_visited} attractions."
        )
    else:
        lines.append("⚠️ Itinerary planned with adjustments needed.")

    lines.append("")

    for day in days:
        lines.append(f"=== Day {day.day_number}: {day.day_of_week} ===")
        for entry in day.entries:
            note_str = f" ({entry.notes})" if entry.notes else ""
            lines.append(
                f"  {entry.start_time}–{entry.end_time} | {entry.name} "
                f"[{entry.activity_type}] ({entry.duration_minutes} min){note_str}"
            )
        lines.append("")

    if adjustments:
        lines.append("Adjustments:")
        for adj in adjustments:
            lines.append(f"- {adj}")
        lines.append("")

    if overflow is not None:
        lines.append(
            f" Time Overflow: Requested {overflow.requested_minutes} min, "
            f"available {overflow.available_minutes} min."
        )
        lines.append(f"Suggestion: {overflow.suggestion}")
        lines.append("")

    if all_conflicts:
        lines.append("Closure Conflicts Detected:")
        for conflict in all_conflicts:
            lines.append(
                f"- {conflict.attraction_name}: closed on "
                f"{conflict.requested_day} ({conflict.suggestion})"
            )

    lines.append(f"\nEstimated total cost: ${total_cost}")

    # ``result`` is constructed for parity with the TS implementation — useful
    # for tests that want to inspect structured output. The tool's return value
    # is the formatted text content, matching the AgentToolResult.content shape.
    _ = result

    return "\n".join(lines)
