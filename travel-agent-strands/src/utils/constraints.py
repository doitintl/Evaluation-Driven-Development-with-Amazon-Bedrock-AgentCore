# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Constraint helpers for the route planner — port of utils/constraints.ts.

These are deterministic helpers used by ``plan_route``. The closure-detection
logic here is the baseline that Module 4 (model swap pedagogy) depends on, so
keep parity with the TypeScript implementation.
"""

from __future__ import annotations

from typing import List, Optional

from ..data.attractions import attractions
from ..data.distances import distances
from ..data.types import Attraction, ClosureConflict


DAYS_OF_WEEK: List[str] = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


def get_day_offset(start_day: str, offset: int) -> str:
    """Return the day of the week ``offset`` days from ``start_day``."""
    if start_day not in DAYS_OF_WEEK:
        return start_day
    start_index = DAYS_OF_WEEK.index(start_day)
    return DAYS_OF_WEEK[(start_index + offset) % 7]


def parse_time_to_minutes(time_str: str) -> int:
    """Parse ``HH:MM`` to total minutes since midnight."""
    hours, minutes = time_str.split(":")
    return int(hours) * 60 + int(minutes)


def find_attraction(name: str) -> Optional[Attraction]:
    """Look up an attraction by name from the mock data."""
    for a in attractions:
        if a.name == name:
            return a
    return None


def is_open_on_day(attraction: Attraction, day_of_week: str) -> bool:
    """Return True if ``attraction`` is open on ``day_of_week``."""
    return day_of_week not in attraction.closure_days


def is_open_at_time(attraction: Attraction, time_str: str) -> bool:
    """Return True if the time falls within ``[open_time, close_time)``."""
    t = parse_time_to_minutes(time_str)
    return parse_time_to_minutes(attraction.open_time) <= t < parse_time_to_minutes(
        attraction.close_time
    )


def get_travel_time(from_name: str, to_name: str) -> int:
    """Look up travel minutes between two attractions; default 60 if missing."""
    if from_name == to_name:
        return 0
    row = distances.get(from_name)
    if row is not None and to_name in row:
        return row[to_name]
    return 60


def detect_closure_conflicts(
    attraction_names: List[str], start_day: str, num_days: int
) -> List[ClosureConflict]:
    """Detect closure conflicts for each attraction on each requested day.

    Mirrors ``detectClosureConflicts`` in constraints.ts: for every (day,
    attraction) pair, if the attraction is closed that day a ``ClosureConflict``
    is appended with a suggestion pointing at the next available day.
    """
    conflicts: List[ClosureConflict] = []

    for day_offset in range(num_days):
        current_day = get_day_offset(start_day, day_offset)
        for name in attraction_names:
            attr = find_attraction(name)
            if attr is None:
                continue
            if not is_open_on_day(attr, current_day):
                # Find a suggestion: the next available day
                suggestion_day = ""
                for next_offset in range(1, 8):
                    candidate_day = get_day_offset(current_day, next_offset)
                    if is_open_on_day(attr, candidate_day):
                        suggestion_day = candidate_day
                        break

                conflicts.append(
                    ClosureConflict(
                        attraction_name=name,
                        requested_day=current_day,
                        closure_days=list(attr.closure_days),
                        suggestion=(
                            f"Reschedule to {suggestion_day} when {name} is open"
                            if suggestion_day
                            else f"{name} has limited availability; check schedule"
                        ),
                    )
                )

    return conflicts
