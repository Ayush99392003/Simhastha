"""
Dummy QR checkpoint scan provider.

QR scanners are placed at P3 redistribution nodes and P1 ghats.
They only capture *compliant* pilgrims who scan their pass.
Fusion weight: 0.20.

The provider back-calculates estimated true crowd from
the compliance factor, introducing uncertainty at high load
when compliance drops (crowd control breaks down).
"""

from __future__ import annotations

import random

from config.settings import (
    BASELINE_OCC,
    EVENT_FACTORS,
    P1_NODES,
    P3_NODES,
)
from ingestion.base import BaseProvider, CrowdSignal

_QR_NODES: frozenset[int] = P3_NODES | P1_NODES

# Pilgrim QR compliance drops as crowd density rises
_COMPLIANCE: dict[str, float] = {
    "normal_day": 0.85,
    "weekend": 0.78,
    "festival_day": 0.68,
    "shahi_snan": 0.55,
}


class DummyQRProvider(BaseProvider):
    """
    Simulates QR-code scan counts at pilgrim checkpoints.
    Under-counts by the scenario compliance factor, then
    back-calculates the inferred true crowd size.
    """

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def emit(
        self,
        scenario: str = "normal_day",
        weather: str = "clear",
    ) -> list[CrowdSignal]:
        ef = EVENT_FACTORS[scenario]
        compliance = _COMPLIANCE.get(scenario, 0.75)
        now = self._now()
        signals: list[CrowdSignal] = []

        for node_id in sorted(_QR_NODES):
            base = BASELINE_OCC[node_id]
            true_crowd = base * ef
            scanned = true_crowd * compliance
            noise = self._rng.gauss(0, scanned * 0.06)
            raw_scans = max(0.0, scanned + noise)

            # Back-infer the true crowd from the scan count
            inferred = raw_scans / compliance if compliance > 0 else raw_scans

            signals.append(
                CrowdSignal(
                    node_id=node_id,
                    timestamp=now,
                    source_type="qr",
                    estimate=round(inferred, 1),
                    confidence=round(compliance * 0.90, 3),
                    status="ok",
                    metadata={
                        "scans_raw": int(raw_scans),
                        "compliance_factor": compliance,
                    },
                )
            )
        return signals
