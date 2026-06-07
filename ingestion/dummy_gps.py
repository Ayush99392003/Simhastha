"""
Dummy GPS density provider.

GPS traces are aggregated from the pilgrim mobile app and provide
coarse zone-level crowd estimates. Fusion weight: 0.10.

Penetration rate (% of pilgrims with the app) drops sharply
during Shahi Snan due to network congestion and app crashes.
"""

from __future__ import annotations

import random

from config.settings import (
    BASELINE_OCC,
    EVENT_FACTORS,
    LOCATION_NODES,
)
from ingestion.base import BaseProvider, CrowdSignal

# GPS works on all non-P5 nodes (buffer zones lack app adoption)
_GPS_NODES: frozenset[int] = frozenset(
    k for k, v in LOCATION_NODES.items() if v[1] != "P5"
)

# App penetration (fraction of crowd with app & GPS on)
_PENETRATION: dict[str, float] = {
    "normal_day": 0.40,
    "weekend": 0.38,
    "festival_day": 0.30,
    "shahi_snan": 0.20,  # network congestion degrades coverage
}


class DummyGPSProvider(BaseProvider):
    """
    Simulates crowd density inference from mobile-app GPS pings.
    High noise (±15 %) — used as a coarse cross-check only.
    """

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def emit(
        self,
        scenario: str = "normal_day",
        weather: str = "clear",
    ) -> list[CrowdSignal]:
        ef = EVENT_FACTORS[scenario]
        penetration = _PENETRATION.get(scenario, 0.30)
        now = self._now()
        signals: list[CrowdSignal] = []

        for node_id in sorted(_GPS_NODES):
            base = BASELINE_OCC[node_id]
            true_crowd = base * ef
            sampled = true_crowd * penetration
            noise = self._rng.gauss(0, sampled * 0.15)
            # Back-infer full crowd from sampled GPS pings
            inferred = max(0.0, (sampled + noise) / penetration)

            signals.append(
                CrowdSignal(
                    node_id=node_id,
                    timestamp=now,
                    source_type="gps",
                    estimate=round(inferred, 1),
                    confidence=round(penetration * 0.75, 3),
                    status="ok",
                    metadata={
                        "app_pings": int(max(0, sampled + noise)),
                        "penetration_rate": penetration,
                    },
                )
            )
        return signals
