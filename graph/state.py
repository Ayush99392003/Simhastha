"""
Dynamic graph state builder.

Constructs a ``networkx.DiGraph`` from the current fused node states
and predictions, applying scenario- and weather-adjusted edge weights.

Dynamic weight formula (matches simhastha_kg_v2.py reference):
    weight = dist_km × event_factor × (1 + congestion) / weather_factor

where ``congestion`` is the source-node occupancy ratio [0, 1].
"""

from __future__ import annotations

from typing import Any

import networkx as nx

from config.settings import (
    BASE_EDGES,
    EVENT_FACTORS,
    LOCATION_NODES,
    WEATHER_FACTORS,
)
from fusion.engine import FusedNodeState
from prediction.forecaster import NodeForecast


def dynamic_weight(
    dist_km: float,
    congestion: float,
    scenario: str,
    weather: str,
) -> float:
    """Compute a dynamic road-segment weight."""
    ef = EVENT_FACTORS[scenario]
    wf = WEATHER_FACTORS[weather]
    return round(dist_km * ef * (1 + congestion) / wf, 2)


def _edge_color(weight: float) -> str:
    if weight > 10:
        return "#FF2D2D"
    if weight > 5:
        return "#FF8C00"
    if weight > 2:
        return "#FFD700"
    return "#444466"


class GraphState:
    """
    Manages the live NetworkX DiGraph of the Ujjain road network.

    ``build()`` is called once per pipeline tick to refresh all
    node attributes and edge weights from the latest fused state.
    """

    def __init__(self) -> None:
        self._graph: nx.DiGraph = nx.DiGraph()

    @property
    def graph(self) -> nx.DiGraph:
        return self._graph

    def build(
        self,
        fused_states: dict[int, FusedNodeState],
        forecasts: dict[int, NodeForecast],
        scenario: str = "normal_day",
        weather: str = "clear",
        approved_closures: set = None,
    ) -> nx.DiGraph:
        """Rebuild the DiGraph from current fused states."""
        if approved_closures is None:
            approved_closures = set()

        G = nx.DiGraph()

        # ── Add location nodes ──────────────────────────────────────────
        for node_id, state in fused_states.items():
            fc = forecasts.get(node_id)
            G.add_node(
                node_id,
                label=state.name,
                priority=state.priority,
                color=state.color,
                risk_level=state.risk_level,
                risk_color=state.risk_color,
                fused_occupancy=state.fused_occupancy,
                effective_capacity=state.effective_capacity,
                safe_threshold=state.safe_threshold,
                load_pct=state.load_pct,
                pred_15min=(fc.pred_15min if fc else state.fused_occupancy),
                pred_30min=(fc.pred_30min if fc else state.fused_occupancy),
                trend=(fc.trend if fc else "stable"),
            )

        # ── Add edges with dynamic weights ──────────────────────────────
        for src, dst, dist_km in BASE_EDGES:
            src_state = fused_states.get(src)
            if src_state and src_state.effective_capacity > 0:
                congestion = (
                    src_state.fused_occupancy / src_state.effective_capacity
                )
            else:
                congestion = 0.5

            if src in approved_closures or dst in approved_closures:
                w = 1e6
            else:
                w = dynamic_weight(dist_km, congestion, scenario, weather)

            col = _edge_color(w)

            G.add_edge(
                src,
                dst,
                weight=w,
                dist_km=dist_km,
                color=col,
                congestion=round(congestion, 3),
            )

        self._graph = G
        return G

    def to_dict(self, approved_closures: set = None) -> dict[str, Any]:
        """Return JSON-serialisable graph representation."""
        if approved_closures is None:
            approved_closures = set()

        G = self._graph
        nodes: list[dict] = []
        for nid, data in G.nodes(data=True):
            name, priority, p_color = LOCATION_NODES.get(
                nid, (str(nid), "P?", "#FFFFFF")
            )
            node_label = data.get("label", name)

            node_shape = "dot"
            lbl = node_label.lower()
            if "temple" in lbl or "ashram" in lbl or "ganesh" in lbl:
                node_shape = "star"
                node_label = "🕉️ " + node_label
            elif "ghat" in lbl:
                node_shape = "hexagon"
                node_label = "🌊 " + node_label
            elif "junction" in lbl or "chowk" in lbl:
                node_shape = "triangle"
                node_label = "🚦 " + node_label
            elif "entry" in lbl or "station" in lbl or "stand" in lbl:
                node_shape = "square"
                node_label = "🚉 " + node_label

            nodes.append(
                {
                    "id": nid,
                    "label": node_label,
                    "shape": node_shape,
                    "priority": data.get("priority", priority),
                    "color": data.get("color", p_color),
                    "risk_level": data.get("risk_level", "LOW"),
                    "risk_color": data.get("risk_color", "#00E676"),
                    "fused_occupancy": round(data.get("fused_occupancy", 0)),
                    "effective_capacity": data.get("effective_capacity", 0),
                    "safe_threshold": data.get("safe_threshold", 0),
                    "load_pct": round(data.get("load_pct", 0), 1),
                    "pred_15min": round(data.get("pred_15min", 0)),
                    "pred_30min": round(data.get("pred_30min", 0)),
                    "trend": data.get("trend", "stable"),
                }
            )

        edges: list[dict] = []
        for src, dst, data in G.edges(data=True):
            w = data.get("weight", 1.0)

            if dst in approved_closures or src in approved_closures:
                gate_status = "🚧 CLOSED (Manual)"
                dashes = True
            elif w > 10:
                gate_status = "🔴 CRITICAL (Gate Open)"
                dashes = False
            else:
                gate_status = "🟢 OPEN"
                dashes = False

            edges.append(
                {
                    "from": src,
                    "to": dst,
                    "weight": w,
                    "dist_km": data.get("dist_km", 0.0),
                    "color": data.get("color", "#444466"),
                    "congestion": data.get("congestion", 0.0),
                    "gate_status": gate_status,
                    "dashes": dashes,
                }
            )

        return {"nodes": nodes, "edges": edges}
