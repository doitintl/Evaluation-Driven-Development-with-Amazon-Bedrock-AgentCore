# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Sites specialist tool — port of agents/sites-agent.ts.

Exports a single ``query_sites`` Strands tool. The function-level docstring
becomes the tool description; argument docstrings become parameter descriptions.
"""

from __future__ import annotations

from typing import List, Optional

from strands import tool

from ..data.attractions import attractions
from ..data.types import Attraction


@tool
def query_sites(query: str, day_of_week: Optional[str] = None) -> str:
    """Query information about attractions in the city including opening hours, closure days, visit duration, ticket prices, and booking requirements. Use this to look up attraction details before planning routes.

    Args:
        query: Search query for attractions (name, category, or 'all').
        day_of_week: Day to check availability (e.g., 'Monday'). When set,
            only attractions open on that day are returned.

    Returns:
        Formatted multi-line text describing the matching attractions.
    """
    filtered: List[Attraction]

    if query.lower() == "all":
        filtered = list(attractions)
    else:
        lower_query = query.lower()
        filtered = [
            a
            for a in attractions
            if lower_query in a.name.lower() or a.category.lower() == lower_query
        ]

    # Filter by day availability if specified
    if day_of_week:
        filtered = [a for a in filtered if day_of_week not in a.closure_days]

    # Build text content with booking advisories
    lines: List[str] = []

    if not filtered:
        lines.append(f'No attractions found matching "{query}".')
    else:
        for attraction in filtered:
            lines.append(f"**{attraction.name}** ({attraction.category})")
            lines.append(f"  {attraction.description}")
            lines.append(f"Hours: {attraction.open_time}–{attraction.close_time}")
            if attraction.closure_days:
                lines.append(f"Closed: {', '.join(attraction.closure_days)}")
            lines.append(
                f"Visit duration: {attraction.visit_duration_minutes} minutes"
            )
            lines.append(f"Ticket price: ${attraction.ticket_price}")

            if attraction.advance_booking_required:
                lines.append(
                    f"  ⚠️ BOOKING ADVISORY: Advance booking is required for "
                    f"{attraction.name}. Reserve tickets before your visit."
                )

            lines.append("")

    return "\n".join(lines)
