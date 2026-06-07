"""
Occupancy fusion engine.

Combines ``CrowdSignal`` batches from multiple sources into a single
``FusedNodeState`` per location node using confidence-weighted averaging.

Fusion formula (per node):
    fused = Σ(signal.estimate × weight × signal.confidence)
            / Σ(weight × signal.confidence)

where ``weight`` is the FUSION_WEIGHTS entry for that source type.

Weather signals (node_id == 0) are consumed separately and used
to compute effective capacity / safe threshold.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config.settings import (
    BASE_CAPACITY,
    BASELINE_OCC,
    EVENT_FACTORS,
    FUSION_WEIGHTS,
    LOCATION_NODES,
    WEATHER_FACTORS,
)
from ingestion.base import CrowdSignal


# ── Output dataclass ─────────────────────────────────────────────────────
@dataclass
class FusedNodeState:
    """
    Complete fused state for one location node.
    Produced by ``FusionEngine.fuse()`` once per pipeline tick.
    """

    node_id: int
    name: str
    priority: str
    color: str
    fused_occupancy: float
    effective_capacity: int
    safe_threshold: int
    risk_level: str
    risk_color: str
    load_pct: float
    source_breakdown: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """JSON-serialisable representation."""
        return {
            "node_id": self.node_id,
            "name": self.name,
            "priority": self.priority,
            "color": self.color,
            "fused_occupancy": round(self.fused_occupancy),
            "effective_capacity": self.effective_capacity,
            "safe_threshold": self.safe_threshold,
            "risk_level": self.risk_level,
            "risk_color": self.risk_color,
            "load_pct": round(self.load_pct, 1),
            "source_breakdown": {
                k: round(v) for k, v in self.source_breakdown.items()
            },
        }


# ── Helpers ──────────────────────────────────────────────────────────────
def _effective_capacity(
    node_id: int,
    weather: str,
    scenario: str,
) -> tuple[int, int]:
    """Return ``(effective_cap, safe_threshold)`` for a node."""
    base = BASE_CAPACITY[node_id]
    wf = WEATHER_FACTORS.get(weather, 1.0)

    node_name = LOCATION_NODES.get(node_id, ("",))[0]
    is_ghat = "Ghat" in node_name
    is_temple = "Temple" in node_name
    is_junction = "Junction" in node_name

    # Location-specific weather penalties to capacity
    if weather in ["heavy_rain", "thunderstorm"] and is_ghat:
        # Ghats become extremely dangerous in heavy rain/thunderstorms
        # due to slippery stairs and rising water levels. Safe capacity drops drastically.
        wf *= 0.5
    elif weather == "light_rain" and is_ghat:
        wf *= 0.8

    # Location-specific scenario penalties to capacity
    if scenario == "fire_breakout" and is_temple:
        wf *= 0.2  # Massive capacity drop due to fire in enclosed spaces
    elif scenario == "structural_failure" and (is_ghat or is_junction):
        wf *= 0.4  # Bridge/barricade collapse makes it highly unsafe
    elif scenario == "vip_visit" and is_temple:
        wf *= 0.6  # VIP security protocols restrict standard capacity

    eff_cap = int(base * wf)
    safe_thr = int(eff_cap * 0.80)
    return eff_cap, safe_thr


def _risk_level(
    occ: float,
    safe_thresh: int,
) -> tuple[str, str]:
    """Return ``(risk_label, hex_color)`` for the given occupancy."""
    ratio = occ / safe_thresh if safe_thresh > 0 else 1.0
    if ratio >= 1.00:
        return "CRITICAL", "#FF2D2D"
    if ratio >= 0.85:
        return "HIGH", "#FF8C00"
    if ratio >= 0.65:
        return "MEDIUM", "#FFD700"
    return "LOW", "#00E676"


# ── Engine ───────────────────────────────────────────────────────────────
class FusionEngine:
    """
    Fuses a heterogeneous list of ``CrowdSignal`` objects into
    a per-node ``FusedNodeState`` dictionary.
    """

    def __init__(self) -> None:
        self.evacuation_factors: dict[int, float] = {}
        self.accumulation_factors: dict[int, float] = {}

    def fuse(
        self,
        signals: list[CrowdSignal],
        scenario: str = "normal_day",
        weather: str = "clear",
        approved_closures: set = None,
    ) -> dict[int, FusedNodeState]:
        if approved_closures is None:
            approved_closures = set()
        """
        Fuse all signals into per-node states.

        Parameters
        ----------
        signals  : Combined signals from all providers this tick.
        scenario : Current event scenario key.
        weather  : Current weather condition key.

        Returns
        -------
        ``dict[node_id, FusedNodeState]`` covering all 25 nodes.
        """
        ok_signals = [s for s in signals if s.status == "ok"]
        crowd_signals = [s for s in ok_signals if s.node_id != 0]

        # Group by node
        by_node: dict[int, list[CrowdSignal]] = {}
        for sig in crowd_signals:
            by_node.setdefault(sig.node_id, []).append(sig)

        results: dict[int, FusedNodeState] = {}

        for node_id, (name, priority, p_color) in LOCATION_NODES.items():
            eff_cap, safe_thresh = _effective_capacity(
                node_id, weather, scenario
            )
            node_sigs = by_node.get(node_id, [])
            fused_occ, breakdown = self._weighted_fuse(
                node_sigs, node_id, scenario, weather, approved_closures
            )

            # Cap at effective capacity
            fused_occ = min(fused_occ, eff_cap)

            risk_lbl, risk_col = _risk_level(fused_occ, safe_thresh)
            load_pct = fused_occ / eff_cap * 100 if eff_cap > 0 else 0.0

            # P1 nodes inherit risk color to signal criticality
            node_color = risk_col if priority == "P1" else p_color

            results[node_id] = FusedNodeState(
                node_id=node_id,
                name=name,
                priority=priority,
                color=node_color,
                fused_occupancy=fused_occ,
                effective_capacity=eff_cap,
                safe_threshold=safe_thresh,
                risk_level=risk_lbl,
                risk_color=risk_col,
                load_pct=load_pct,
                source_breakdown=breakdown,
            )

        return results

    # ── private ──────────────────────────────────────────────────────────
    def _weighted_fuse(
        self,
        signals: list[CrowdSignal],
        node_id: int,
        scenario: str,
        weather: str,
        approved_closures: set,
    ) -> tuple[float, dict[str, float]]:
        """Confidence-weighted average for a single node."""
        if not signals:
            base = BASELINE_OCC.get(node_id, 0)
            ef = EVENT_FACTORS.get(scenario, 1.0)
            fallback = float(base * ef)
            fused_occ = fallback
            breakdown = {"baseline": fallback}
        else:
            total_w = 0.0
            w_sum = 0.0
            breakdown = {}

            for sig in signals:
                src_w = FUSION_WEIGHTS.get(sig.source_type, 0.05)
                eff_w = src_w * sig.confidence
                w_sum += sig.estimate * eff_w
                total_w += eff_w
                breakdown[sig.source_type] = sig.estimate

            if total_w == 0:
                base = BASELINE_OCC.get(node_id, 0)
                ef = EVENT_FACTORS.get(scenario, 1.0)
                fallback = float(base * ef)
                fused_occ = fallback
                breakdown = {"baseline": fallback}
            else:
                fused_occ = w_sum / total_w

        # --- Natural Dynamics & Crisis Physics ---
        node_name = LOCATION_NODES.get(node_id, ("",))[0]
        is_ghat = "Ghat" in node_name
        is_temple = "Temple" in node_name
        is_junction = "Junction" in node_name
        is_buffer = (
            "Tent" in node_name
            or "Area" in node_name
            or "Parking" in node_name
        )

        if weather in ["light_rain", "heavy_rain", "thunderstorm"] and is_ghat:
            fused_occ *= 0.5
        elif weather == "hot_wave":
            if is_ghat:
                fused_occ *= 1.3
            elif is_temple:
                fused_occ *= 0.8

        # Scenario physics (panic, fleeing)
        if scenario == "stampede_rumor":
            if is_temple or is_ghat:
                fused_occ *= (
                    0.4  # People frantically flee the central core zones
                )
            elif is_junction or is_buffer:
                fused_occ *= (
                    2.5  # People pile up dangerously in the exits and buffers
                )
        elif scenario == "fire_breakout":
            if is_temple:
                fused_occ *= 0.1  # Complete evacuation of temples
            elif is_buffer:
                fused_occ *= 1.5
        elif scenario == "structural_failure":
            if is_ghat:
                fused_occ *= 0.2
            elif is_junction:
                fused_occ *= 2.0

        # --- Evacuation & Accumulation Physics ---
        if node_id in approved_closures:
            # Gates closed: Evacuate crowd
            curr = self.evacuation_factors.get(node_id, 1.0)
            curr = max(0.1, curr * 0.90)  # drop by 10% per tick
            self.evacuation_factors[node_id] = curr

            # Stop accumulation
            self.accumulation_factors[node_id] = 1.0
        else:
            # Gates open: Recover evacuation
            curr = self.evacuation_factors.get(node_id, 1.0)
            if curr < 1.0:
                curr = min(1.0, curr * 1.05)  # recover by 5%
                self.evacuation_factors[node_id] = curr

            # If there's a major event, crowd constantly accumulates if gates aren't closed
            ef = EVENT_FACTORS.get(scenario, 1.0)
            if ef > 1.0:
                acc = self.accumulation_factors.get(node_id, 1.0)
                acc = min(
                    2.5, acc * 1.03
                )  # Crowd grows by 3% per tick, up to 250% base capacity!
                self.accumulation_factors[node_id] = acc
            else:
                self.accumulation_factors[node_id] = 1.0

        fused_occ *= self.evacuation_factors.get(node_id, 1.0)
        fused_occ *= self.accumulation_factors.get(node_id, 1.0)

        return fused_occ, breakdown
