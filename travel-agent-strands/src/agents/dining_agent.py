# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Dining specialist tool — port of agents/dining-agent.ts.

Exports a single ``suggest_dining`` Strands tool. Restaurants are filtered by
meal type and proximity to a named attraction, then sorted by travel time.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from strands import tool

from ..data.restaurants import restaurants
from ..data.types import DiningRecommendation


@tool
def suggest_dining(
    attraction_name: str,
    meal_type: Literal["breakfast", "lunch", "dinner"],
    cuisine_preference: Optional[str] = None,
) -> str:
    """Suggest restaurants near a planned attraction appropriate for the specified meal type. Returns options with cuisine, price range, and travel time from the attraction.

    Args:
        attraction_name: Current or next attraction to find dining near.
        meal_type: Type of meal — one of 'breakfast', 'lunch', 'dinner'.
        cuisine_preference: Optional preferred cuisine type (matched
            case-insensitively); preferred cuisines are sorted first.

    Returns:
        Formatted multi-line text listing restaurant options.
    """
    # 1. Filter restaurants that serve the specified meal_type
    meal_filtered = [r for r in restaurants if meal_type in r.meal_types]

    # 2. Filter restaurants that are near the specified attraction
    nearby_filtered = [
        r
        for r in meal_filtered
        if any(na["attractionName"] == attraction_name for na in r.near_attractions)
    ]

    # 3. Build recommendations with travel time from the attraction
    recommendations: List[DiningRecommendation] = []
    for r in nearby_filtered:
        near_entry = next(
            na for na in r.near_attractions if na["attractionName"] == attraction_name
        )
        reasons = [
            f"Serves {meal_type}",
            f"{near_entry['travelTimeMinutes']} minutes from {attraction_name}",
            f"{r.cuisine_type} cuisine",
        ]
        recommendations.append(
            DiningRecommendation(
                restaurant=r,
                travel_time_from_attraction=near_entry["travelTimeMinutes"],
                match_reason=", ".join(reasons),
            )
        )

    # 4 & 5. Cuisine grouping then per-group sort by travel time
    if cuisine_preference:
        pref_lower = cuisine_preference.lower()
        preferred = [
            rec
            for rec in recommendations
            if rec.restaurant.cuisine_type.lower() == pref_lower
        ]
        others = [
            rec
            for rec in recommendations
            if rec.restaurant.cuisine_type.lower() != pref_lower
        ]
        preferred.sort(key=lambda x: x.travel_time_from_attraction)
        others.sort(key=lambda x: x.travel_time_from_attraction)
        recommendations = preferred + others
    else:
        recommendations.sort(key=lambda x: x.travel_time_from_attraction)

    # 6. Build text content for the model
    if recommendations:
        lines = [
            f"{i + 1}. {rec.restaurant.name} ({rec.restaurant.cuisine_type}, "
            f"{rec.restaurant.price_range}) - {rec.travel_time_from_attraction} min "
            f"from {attraction_name}. {rec.match_reason}"
            for i, rec in enumerate(recommendations)
        ]
        return "\n".join(lines)
    return f"No restaurants found serving {meal_type} near {attraction_name}."
