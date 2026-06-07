"""
Dummy volunteer observation provider.

Volunteer reports are low-frequency, high-variance human
observations at P1 / P2 / P3 nodes. Fusion weight: 0.10.

Volunteers do NOT report every tick (~60 % coverage per tick),
and their estimates carry ±20 % human-perception error.
They add a qualitative ``observation_class`` that can trigger
manual alerts independent of the fusion pipeline.
"""

from __future__ import annotations

import random

from config.settings import (
    BASELINE_OCC,
    EVENT_FACTORS,
    P1_NODES,
    P2_NODES,
    P3_NODES,
)
from ingestion.base import BaseProvider, CrowdSignal

_VOLUNTEER_NODES: frozenset[int] = P1_NODES | P2_NODES | P3_NODES
_REPORT_PROB: float = 0.60  # probability of report per node per tick


def _classify(ratio: float) -> str:
    if ratio >= 1.0:
        return "CRITICAL"
    if ratio >= 0.85:
        return "HIGH"
    if ratio >= 0.65:
        return "MEDIUM"
    return "LOW"


class DummyVolunteerProvider(BaseProvider):
    """
    Simulates human volunteer crowd-observation reports.
    High variance; not every node reports every tick.
    """

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def emit(
        self,
        scenario: str = "normal_day",
        weather: str = "clear",
    ) -> list[CrowdSignal]:
        ef = EVENT_FACTORS[scenario]
        now = self._now()
        signals: list[CrowdSignal] = []

        for node_id in sorted(_VOLUNTEER_NODES):
            # Volunteers don't always file a report each tick
            if self._rng.random() > _REPORT_PROB:
                continue

            base = BASELINE_OCC[node_id]
            true_crowd = base * ef
            # ±20 % human estimation error
            noise = self._rng.gauss(0, true_crowd * 0.20)
            estimate = max(0.0, true_crowd + noise)

            ratio = estimate / true_crowd if true_crowd > 0 else 0.0
            obs_class = _classify(ratio)

            signals.append(
                CrowdSignal(
                    node_id=node_id,
                    timestamp=now,
                    source_type="volunteer",
                    estimate=round(estimate, 1),
                    confidence=0.65,
                    status="ok",
                    metadata={
                        "observation_class": obs_class,
                        "volunteer_id": self._rng.randint(1000, 9999),
                    },
                )
            )
        return signals
