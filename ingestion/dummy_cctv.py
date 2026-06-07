"""
Dummy CCTV / Camera-AI crowd density provider.

Camera AI estimates crowd density at P1 (critical) and P2
(religious corridor) nodes. Fusion weight: 0.25.

Confidence degrades in rain because lens occlusion reduces
detection accuracy.
"""

from __future__ import annotations

import random

from config.settings import (
    BASELINE_OCC,
    EVENT_FACTORS,
    P1_NODES,
    P2_NODES,
    WEATHER_FACTORS,
)
from ingestion.base import BaseProvider, CrowdSignal

_CCTV_NODES: frozenset[int] = P1_NODES | P2_NODES


class DummyCCTVProvider(BaseProvider):
    """
    Simulates camera-based AI crowd-density estimates at all
    P1 and P2 nodes (10 nodes total).
    """

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def emit(
        self,
        scenario: str = "normal_day",
        weather: str = "clear",
    ) -> list[CrowdSignal]:
        ef = EVENT_FACTORS[scenario]
        wf = WEATHER_FACTORS[weather]
        now = self._now()
        signals: list[CrowdSignal] = []

        # Baseline confidence drops in poor visibility
        base_conf = max(0.55, 0.85 - (1.0 - wf) * 0.5)

        for node_id in sorted(_CCTV_NODES):
            base = BASELINE_OCC[node_id]
            scaled = base * ef * wf
            # ±8 % noise — slightly less accurate than gate counters
            noise = self._rng.gauss(0, scaled * 0.08)
            estimate = max(0.0, scaled + noise)

            conf = float(
                min(0.95, max(0.40, base_conf + self._rng.gauss(0, 0.04)))
            )
            # Occlusion increases with rain
            occlusion = round((1.0 - wf) * 40 + self._rng.gauss(0, 2), 1)

            signals.append(
                CrowdSignal(
                    node_id=node_id,
                    timestamp=now,
                    source_type="cctv",
                    estimate=round(estimate, 1),
                    confidence=round(conf, 3),
                    status="ok",
                    metadata={
                        "fps_processed": 25,
                        "occlusion_pct": occlusion,
                    },
                )
            )
        return signals
