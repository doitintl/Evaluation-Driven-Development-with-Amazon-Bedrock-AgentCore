"""Shared dataclass / TypedDict definitions mirroring the pi-mono TS interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, TypedDict


@dataclass
class Attraction:
    """A Luminara attraction with hours, closure days, price, and booking flag."""

    name: str
    description: str
    open_time: str  # HH:MM format
    close_time: str  # HH:MM format
    closure_days: List[str]  # e.g., ["Monday", "Tuesday"]
    visit_duration_minutes: int  # 30-180
    ticket_price: int  # USD
    advance_booking_required: bool
    category: str  # e.g., "history", "art", "nature"


class NearAttraction(TypedDict):
    attractionName: str
    travelTimeMinutes: int


@dataclass
class Restaurant:
    """A Luminara restaurant with cuisine, meal types, price range, and proximity data."""

    name: str
    cuisine_type: str
    meal_types: List[Literal["breakfast", "lunch", "dinner"]]
    price_range: Literal["budget", "moderate", "upscale"]
    near_attractions: List[NearAttraction]


# Distance matrix is a nested dict: {from: {to: minutes}}
DistanceMatrix = Dict[str, Dict[str, int]]


@dataclass
class ItineraryEntry:
    start_time: str  # HH:MM
    end_time: str  # HH:MM
    name: str
    activity_type: Literal["visit", "meal", "travel"]
    duration_minutes: int
    notes: Optional[str] = None


@dataclass
class DayPlan:
    day_number: int
    day_of_week: str
    entries: List[ItineraryEntry] = field(default_factory=list)


@dataclass
class Itinerary:
    days: List[DayPlan]
    total_cost: int
    total_attractions: int
    adjustments: List[str] = field(default_factory=list)


@dataclass
class ClosureConflict:
    attraction_name: str
    requested_day: str
    closure_days: List[str]
    suggestion: str


@dataclass
class TimeOverflow:
    requested_minutes: int
    available_minutes: int
    suggestion: str


@dataclass
class RouteResult:
    success: bool
    itinerary: Optional[Itinerary] = None
    conflicts: Optional[List[ClosureConflict]] = None
    overflow: Optional[TimeOverflow] = None
    adjustments: Optional[List[str]] = None


@dataclass
class DiningRecommendation:
    restaurant: Restaurant
    travel_time_from_attraction: int
    match_reason: str
