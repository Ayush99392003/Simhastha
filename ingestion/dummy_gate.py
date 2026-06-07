"""
Dummy gate counter provider.

Gate counters monitor entry / exit at the five P4 gateway nodes.
They carry the **highest** fusion weight (0.35) because physical
turnstile counts are the most accurate crowd measure available.
"""

from __future__ import annotations

import random

from config.settings import BASELINE_OCC, EVENT_FACTORS, P4_NODES
from ingestion.base import BaseProvider, CrowdSignal


class DummyGateProvider(BaseProvider):
    """
    Simulates IR-beam / turnstile gate counters
    at all P4 entry / exit gateways (nodes 16–20).
    """

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    # ── public API ────────────────────────────────────────────────────────
    def emit(
        self,
        scenario: str = "normal_day",
        weather: str = "clear",
    ) -> list[CrowdSignal]:
        """Return one CrowdSignal per P4 gateway node."""
        ef = EVENT_FACTORS[scenario]
        now = self._now()
        signals: list[CrowdSignal] = []

        for node_id in sorted(P4_NODES):
            base = BASELINE_OCC[node_id]
            scaled = base * ef
            # ±5 % Gaussian noise — gate counters are very accurate
            noise = self._rng.gauss(0, scaled * 0.05)
            estimate = max(0.0, scaled + noise)

            entry = int(estimate * self._rng.uniform(0.08, 0.12))
            exit_ = int(estimate * self._rng.uniform(0.06, 0.10))

            signals.append(
                CrowdSignal(
                    node_id=node_id,
                    timestamp=now,
                    source_type="gate",
                    estimate=round(estimate, 1),
                    confidence=0.92,
                    status="ok",
                    metadata={
                        "entry_delta": entry,
                        "exit_delta": exit_,
                        "net_flow": entry - exit_,
                    },
                )
            )
        return signals
