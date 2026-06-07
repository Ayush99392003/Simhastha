"""
Data contract for all crowd signal providers.

Every source — real or dummy — must emit ``CrowdSignal`` objects
before data enters the fusion engine.  This keeps the fusion layer
completely independent of the underlying source implementation.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# ── Allowed values ───────────────────────────────────────────────────────
_VALID_SOURCES: frozenset[str] = frozenset(
    {"cctv", "qr", "gps", "gate", "weather", "volunteer"}
)
_VALID_STATUSES: frozenset[str] = frozenset({"ok", "stale", "error"})


@dataclass
class CrowdSignal:
    """
    Canonical crowd observation emitted by any data source.

    Parameters
    ----------
    node_id     : Location node (1–25). Use 0 for broadcast signals
                  (e.g. weather) that apply to all nodes.
    timestamp   : UTC time of the reading.
    source_type : One of cctv | qr | gps | gate | weather | volunteer.
    estimate    : Crowd count (people) or dimensionless factor.
    confidence  : Source reliability in [0.0, 1.0].
    status      : ``ok`` | ``stale`` | ``error``.
    metadata    : Source-specific extras (free-form dict).
    """

    node_id: int
    timestamp: datetime
    source_type: str
    estimate: float
    confidence: float
    status: str = "ok"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"confidence must be in [0, 1]; got {self.confidence}"
            )
        if self.status not in _VALID_STATUSES:
            raise ValueError(
                f"invalid status {self.status!r}; "
                f"choose from {_VALID_STATUSES}"
            )
        if self.source_type not in _VALID_SOURCES:
            raise ValueError(
                f"invalid source_type {self.source_type!r}; "
                f"choose from {_VALID_SOURCES}"
            )


class BaseProvider(abc.ABC):
    """Abstract base class for all crowd signal providers."""

    @abc.abstractmethod
    def emit(
        self,
        scenario: str = "normal_day",
        weather: str = "clear",
    ) -> list[CrowdSignal]:
        """Return the current batch of crowd signals."""
        ...

    @staticmethod
    def _now() -> datetime:
        """Return current UTC timestamp."""
        return datetime.now(tz=timezone.utc)
