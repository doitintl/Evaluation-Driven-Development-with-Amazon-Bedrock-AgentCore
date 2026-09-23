"""Mock Luminara restaurants — verbatim port of restaurants.ts."""

from __future__ import annotations

from typing import List

from .types import Restaurant


restaurants: List[Restaurant] = [
    Restaurant(
        name="Sunrise Terrace Café",
        cuisine_type="Mediterranean",
        meal_types=["breakfast", "lunch"],
        price_range="budget",
        near_attractions=[
            {"attractionName": "Botanical Gardens", "travelTimeMinutes": 4},
            {"attractionName": "Skyline Tower", "travelTimeMinutes": 8},
            {"attractionName": "Science Discovery Center", "travelTimeMinutes": 10},
        ],
    ),
    Restaurant(
        name="Dragon Bowl Noodle House",
        cuisine_type="Asian",
        meal_types=["lunch", "dinner"],
        price_range="budget",
        near_attractions=[
            {"attractionName": "Night Market", "travelTimeMinutes": 3},
            {"attractionName": "Old Quarter Walking Tour", "travelTimeMinutes": 6},
            {"attractionName": "Ancient Temple Ruins", "travelTimeMinutes": 9},
        ],
    ),
    Restaurant(
        name="Palazzo Dining Room",
        cuisine_type="Italian",
        meal_types=["lunch", "dinner"],
        price_range="upscale",
        near_attractions=[
            {"attractionName": "Royal Palace", "travelTimeMinutes": 5},
            {"attractionName": "Grand Museum of Luminara", "travelTimeMinutes": 7},
            {"attractionName": "Luminara Art Gallery", "travelTimeMinutes": 11},
        ],
    ),
    Restaurant(
        name="Harbor Fresh Kitchen",
        cuisine_type="Seafood",
        meal_types=["lunch", "dinner"],
        price_range="moderate",
        near_attractions=[
            {"attractionName": "Harbor Cruise", "travelTimeMinutes": 3},
            {"attractionName": "Skyline Tower", "travelTimeMinutes": 10},
            {"attractionName": "Night Market", "travelTimeMinutes": 12},
            {"attractionName": "Old Quarter Walking Tour", "travelTimeMinutes": 14},
        ],
    ),
    Restaurant(
        name="The Golden Croissant",
        cuisine_type="French",
        meal_types=["breakfast", "lunch"],
        price_range="moderate",
        near_attractions=[
            {"attractionName": "Grand Museum of Luminara", "travelTimeMinutes": 4},
            {"attractionName": "Luminara Art Gallery", "travelTimeMinutes": 6},
            {"attractionName": "Royal Palace", "travelTimeMinutes": 12},
        ],
    ),
    Restaurant(
        name="Ember & Vine Steakhouse",
        cuisine_type="American",
        meal_types=["dinner"],
        price_range="upscale",
        near_attractions=[
            {"attractionName": "Skyline Tower", "travelTimeMinutes": 5},
            {"attractionName": "Science Discovery Center", "travelTimeMinutes": 8},
            {"attractionName": "Botanical Gardens", "travelTimeMinutes": 13},
            {"attractionName": "Harbor Cruise", "travelTimeMinutes": 15},
        ],
    ),
]
