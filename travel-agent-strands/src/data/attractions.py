"""Mock Luminara attractions — verbatim port of attractions.ts."""

from __future__ import annotations

from typing import List

from .types import Attraction


attractions: List[Attraction] = [
    Attraction(
        name="Grand Museum of Luminara",
        description=(
            "A sprawling museum housing centuries of Luminaran history, "
            "from ancient artifacts to modern art installations."
        ),
        open_time="09:00",
        close_time="18:00",
        closure_days=["Monday"],
        visit_duration_minutes=120,
        ticket_price=25,
        advance_booking_required=False,
        category="history",
    ),
    Attraction(
        name="Royal Palace",
        description=(
            "The former seat of the Luminaran monarchy, featuring opulent "
            "throne rooms and manicured courtyards."
        ),
        open_time="10:00",
        close_time="17:00",
        closure_days=["Tuesday"],
        visit_duration_minutes=90,
        ticket_price=35,
        advance_booking_required=True,
        category="history",
    ),
    Attraction(
        name="Skyline Tower",
        description=(
            "A 360-degree observation deck offering panoramic views of the "
            "city and surrounding coastline."
        ),
        open_time="08:00",
        close_time="22:00",
        closure_days=[],
        visit_duration_minutes=60,
        ticket_price=20,
        advance_booking_required=False,
        category="entertainment",
    ),
    Attraction(
        name="Botanical Gardens",
        description=(
            "Lush tropical and temperate gardens spread across 30 acres "
            "with rare plant species from around the world."
        ),
        open_time="07:00",
        close_time="19:00",
        closure_days=[],
        visit_duration_minutes=90,
        ticket_price=12,
        advance_booking_required=False,
        category="nature",
    ),
    Attraction(
        name="Old Quarter Walking Tour",
        description=(
            "A guided stroll through cobblestone streets lined with historic "
            "buildings, local shops, and street performers."
        ),
        open_time="09:00",
        close_time="16:00",
        closure_days=["Sunday"],
        visit_duration_minutes=150,
        ticket_price=18,
        advance_booking_required=False,
        category="culture",
    ),
    Attraction(
        name="Luminara Art Gallery",
        description=(
            "A contemporary gallery showcasing rotating exhibitions from "
            "local and international artists."
        ),
        open_time="10:00",
        close_time="18:00",
        closure_days=["Monday", "Wednesday"],
        visit_duration_minutes=75,
        ticket_price=15,
        advance_booking_required=False,
        category="art",
    ),
    Attraction(
        name="Harbor Cruise",
        description=(
            "A scenic boat tour along the Luminaran coastline with views "
            "of sea cliffs and the historic lighthouse."
        ),
        open_time="10:00",
        close_time="15:00",
        closure_days=[],
        visit_duration_minutes=60,
        ticket_price=40,
        advance_booking_required=True,
        category="entertainment",
    ),
    Attraction(
        name="Night Market",
        description=(
            "A vibrant open-air market with street food stalls, live music, "
            "and handcrafted souvenirs under lantern light."
        ),
        open_time="18:00",
        close_time="23:00",
        closure_days=["Monday", "Tuesday", "Wednesday", "Thursday"],
        visit_duration_minutes=90,
        ticket_price=0,
        advance_booking_required=False,
        category="culture",
    ),
    Attraction(
        name="Science Discovery Center",
        description=(
            "An interactive science museum with hands-on exhibits covering "
            "physics, biology, and space exploration."
        ),
        open_time="09:00",
        close_time="17:00",
        closure_days=[],
        visit_duration_minutes=90,
        ticket_price=22,
        advance_booking_required=False,
        category="science",
    ),
    Attraction(
        name="Ancient Temple Ruins",
        description=(
            "Well-preserved ruins of a 2,000-year-old temple complex set "
            "on a hillside overlooking the harbor."
        ),
        open_time="06:00",
        close_time="18:00",
        closure_days=[],
        visit_duration_minutes=45,
        ticket_price=10,
        advance_booking_required=False,
        category="history",
    ),
]
