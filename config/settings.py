"""
Central configuration for Simhastha Ujjain 2028.
Data sourced from simhastha_kg_v2.py (reference file — unchanged).
All constants here are the single source of truth for the pipeline.
"""

from __future__ import annotations

EVENT_FACTORS: dict[str, float] = {
    "normal_day": 1.0,
    "weekend": 1.4,
    "parikrama": 1.8,
    "ekadashi": 2.0,
    "festival_day": 2.5,
    "purnima": 2.5,
    "somvati_amavasya": 3.0,
    "mahashivratri": 6.0,
    "shahi_snan": 8.0,
    "vip_visit": 1.2,
    "stampede_rumor": 1.5,
    "fire_breakout": 1.2,
    "structural_failure": 1.1,
}

WEATHER_FACTORS: dict[str, float] = {
    "clear": 1.0,
    "pleasant": 1.2,
    "hot_wave": 0.7,
    "light_rain": 0.8,
    "heavy_rain": 0.6,
    "thunderstorm": 0.4,
}

# ── Base node capacities (people, normal-day no-rain) ────────────────────
BASE_CAPACITY: dict[int, int] = {
    1: 25000,
    2: 18000,
    3: 15000,
    4: 20000,
    5: 30000,
    6: 12000,
    7: 10000,
    8: 8000,
    9: 9000,
    10: 6000,
    11: 5000,
    12: 5000,
    13: 6000,
    14: 5000,
    15: 4000,
    16: 20000,
    17: 15000,
    18: 10000,
    19: 10000,
    20: 8000,
    21: 30000,
    22: 20000,
    23: 25000,
    24: 40000,
    25: 35000,
}

# ── Simulated baseline occupancy (normal day) ────────────────────────────
BASELINE_OCC: dict[int, int] = {
    1: 15000,
    2: 12000,
    3: 9000,
    4: 12000,
    5: 18000,
    # 3 nodes specifically set to critical for realistic starting conditions
    6: 12500,
    7: 10500,
    8: 8500,
    # Rest normal / safe
    9: 6500,
    10: 4500,
    11: 3500,
    12: 3500,
    13: 4500,
    14: 3500,
    15: 3000,
    16: 11000,
    17: 8500,
    18: 5200,
    19: 4800,
    20: 3900,
    21: 8000,
    22: 3000,
    23: 6000,
    24: 9000,
    25: 7500,
}

# ── Fusion weights (must sum to 1.0) ─────────────────────────────────────
FUSION_WEIGHTS: dict[str, float] = {
    "gate": 0.35,
    "cctv": 0.25,
    "qr": 0.20,
    "gps": 0.10,
    "volunteer": 0.10,
}

# ── Location nodes: id → (name, priority, hex_color) ────────────────────
LOCATION_NODES: dict[int, tuple[str, str, str]] = {
    # P1 – Critical Zones
    1: ("Ram Ghat", "P1", "#FF2D2D"),
    2: ("Datt Akhada Ghat", "P1", "#FF2D2D"),
    3: ("Narsingh Ghat", "P1", "#FF2D2D"),
    4: ("Triveni Ghat", "P1", "#FF2D2D"),
    5: ("Mahakaleshwar Temple", "P1", "#FF2D2D"),
    # P2 – Religious Corridors
    6: ("Harsiddhi Temple", "P2", "#FF8C00"),
    7: ("Kal Bhairav Temple", "P2", "#FF8C00"),
    8: ("Mangalnath Temple", "P2", "#FF8C00"),
    9: ("Chintaman Ganesh", "P2", "#FF8C00"),
    10: ("Sandipani Ashram", "P2", "#FF8C00"),
    # P3 – Redistribution Nodes
    11: ("Freeganj Junction", "P3", "#FFD700"),
    12: ("Dewas Gate Junction", "P3", "#FFD700"),
    13: ("Tower Chowk", "P3", "#FFD700"),
    14: ("Nanakheda Junction", "P3", "#FFD700"),
    15: ("Kothi Road Junction", "P3", "#FFD700"),
    # P4 – Entry/Exit Gateways
    16: ("Ujjain Railway Station", "P4", "#00C5FF"),
    17: ("Nanakheda Bus Stand", "P4", "#00C5FF"),
    18: ("Indore Road Entry", "P4", "#00C5FF"),
    19: ("Dewas Road Entry", "P4", "#00C5FF"),
    20: ("Agar Road Entry", "P4", "#00C5FF"),
    # P5 – Buffer / Holding Areas
    21: ("Tent City North", "P5", "#00E676"),
    22: ("Emergency Holding Area", "P5", "#00E676"),
    23: ("Tent City South", "P5", "#00E676"),
    24: ("Overflow Parking", "P5", "#00E676"),
    25: ("Accommodation Zone", "P5", "#00E676"),
}

# ── Priority node sets ───────────────────────────────────────────────────
P1_NODES: frozenset[int] = frozenset(
    k for k, v in LOCATION_NODES.items() if v[1] == "P1"
)
P2_NODES: frozenset[int] = frozenset(
    k for k, v in LOCATION_NODES.items() if v[1] == "P2"
)
P3_NODES: frozenset[int] = frozenset(
    k for k, v in LOCATION_NODES.items() if v[1] == "P3"
)
P4_NODES: frozenset[int] = frozenset(
    k for k, v in LOCATION_NODES.items() if v[1] == "P4"
)
P5_NODES: frozenset[int] = frozenset(
    k for k, v in LOCATION_NODES.items() if v[1] == "P5"
)

# ── Road network edges: (src, dst, distance_km) ──────────────────────────
BASE_EDGES: list[tuple[int, int, float]] = [
    (16, 11, 0.8),
    (16, 14, 1.2),
    (17, 14, 0.3),
    (18, 12, 1.5),
    (19, 12, 0.9),
    (20, 15, 2.1),
    (11, 13, 0.6),
    (12, 13, 0.7),
    (13, 14, 0.9),
    (14, 15, 1.1),
    (15, 11, 1.4),
    (13, 5, 0.5),
    (11, 7, 0.9),
    (12, 8, 1.3),
    (14, 9, 1.7),
    (15, 10, 2.0),
    (5, 1, 0.4),
    (5, 2, 0.6),
    (7, 3, 0.8),
    (6, 1, 0.5),
    (6, 4, 0.7),
    (8, 4, 1.1),
    (9, 3, 1.3),
    (10, 4, 1.6),
    (1, 2, 0.3),
    (2, 3, 0.4),
    (3, 4, 0.5),
    (14, 21, 0.8),
    (15, 23, 1.2),
    (12, 22, 1.0),
    (11, 24, 0.9),
    (13, 25, 1.5),
]

# ── Pipeline runtime settings ────────────────────────────────────────────
import os
TICK_INTERVAL_SECONDS: int = 30
API_HOST: str = "0.0.0.0"
API_PORT: int = int(os.getenv("PORT", 7860))

# ── Forecaster settings ──────────────────────────────────────────────────
EMA_ALPHA: float = 0.3
HISTORY_WINDOW: int = 10
