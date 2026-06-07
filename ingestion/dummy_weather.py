"""
Dummy weather feed provider.

The weather signal is a broadcast — it does NOT carry a per-node
crowd count but a dimensionless factor used by the fusion engine
to scale effective node capacity.  node_id = 0 is the convention
for a system-wide broadcast signal.
"""

from __future__ import annotations

from config.settings import WEATHER_FACTORS
from ingestion.base import BaseProvider, CrowdSignal

_BROADCAST_NODE = 0  # sentinel: applies to all location nodes


class DummyWeatherProvider(BaseProvider):
    """
    Simulates a weather API feed.

    The ``weather`` argument passed to ``emit()`` is the externally
    controlled condition (set by the pipeline CLI or /api/scenario).
    This provider wraps it in a CrowdSignal so the fusion engine
    consumes it through the same contract as every other source.
    """

    def emit(
        self,
        scenario: str = "normal_day",
        weather: str = "clear",
    ) -> list[CrowdSignal]:
        factor = WEATHER_FACTORS[weather]

        return [
            CrowdSignal(
                node_id=_BROADCAST_NODE,
                timestamp=self._now(),
                source_type="weather",
                estimate=factor,
                confidence=0.98,
                status="ok",
                metadata={
                    "condition": weather,
                    "factor": factor,
                },
            )
        ]
