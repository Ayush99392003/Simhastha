"""
Route optimizer and congestion alert engine.

Uses Dijkstra's algorithm on the live dynamic graph to find the
lowest-weight (safest / fastest) path between two nodes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import networkx as nx

from config.settings import LOCATION_NODES


# ── Dataclasses ──────────────────────────────────────────────────────────
@dataclass
class RouteResult:
    """A computed safe route between two nodes."""

    source: int
    destination: int
    path: list[int]
    path_labels: list[str]
    total_weight: float
    total_dist_km: float
    hops: int
    safe: bool  # True if no CRITICAL node in path

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "destination": self.destination,
            "path": self.path,
            "path_labels": self.path_labels,
            "total_weight": round(self.total_weight, 2),
            "total_dist_km": round(self.total_dist_km, 2),
            "hops": self.hops,
            "safe": self.safe,
        }


@dataclass
class CongestionAlert:
    """A congestion alert for a single node."""

    node_id: int
    name: str
    risk_level: str
    risk_color: str
    load_pct: float
    fused_occupancy: float
    effective_capacity: int
    recommended_diversion: list[int] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "risk_level": self.risk_level,
            "risk_color": self.risk_color,
            "load_pct": round(self.load_pct, 1),
            "fused_occupancy": round(self.fused_occupancy),
            "effective_capacity": self.effective_capacity,
            "recommended_diversion": self.recommended_diversion,
        }


# ── Router ───────────────────────────────────────────────────────────────
class Router:
    """
    Computes safe routes and detects congestion on the live graph.
    All methods are stateless — pass the current ``nx.DiGraph`` each time.
    """

    def safe_route(
        self,
        G: nx.DiGraph,
        src: int,
        dst: int,
    ) -> RouteResult | None:
        """
        Shortest path (by dynamic weight) from src to dst.
        Returns None when no path exists.
        """
        if src not in G or dst not in G:
            return None

        try:
            path = nx.dijkstra_path(G, src, dst, weight="weight")
            total_w = nx.dijkstra_path_length(G, src, dst, weight="weight")
        except nx.NetworkXNoPath:
            return None

        total_dist = sum(
            G[path[i]][path[i + 1]].get("dist_km", 0.0)
            for i in range(len(path) - 1)
        )
        path_labels = [
            LOCATION_NODES.get(n, (str(n), "", ""))[0] for n in path
        ]
        safe = all(
            G.nodes[n].get("risk_level", "LOW") != "CRITICAL" for n in path
        )

        return RouteResult(
            source=src,
            destination=dst,
            path=path,
            path_labels=path_labels,
            total_weight=total_w,
            total_dist_km=total_dist,
            hops=len(path) - 1,
            safe=safe,
        )

    def congestion_alerts(
        self,
        G: nx.DiGraph,
    ) -> list[CongestionAlert]:
        """
        Return alerts for every HIGH or CRITICAL node,
        sorted by load_pct descending.
        """
        alerts: list[CongestionAlert] = []

        for node_id, data in G.nodes(data=True):
            risk = data.get("risk_level", "LOW")
            if risk not in {"HIGH", "CRITICAL"}:
                continue

            diversion = self._nearest_buffer(G, node_id)

            alerts.append(
                CongestionAlert(
                    node_id=node_id,
                    name=data.get("label", str(node_id)),
                    risk_level=risk,
                    risk_color=data.get("risk_color", "#FF2D2D"),
                    load_pct=data.get("load_pct", 100.0),
                    fused_occupancy=data.get("fused_occupancy", 0.0),
                    effective_capacity=data.get("effective_capacity", 1),
                    recommended_diversion=diversion,
                )
            )

        alerts.sort(key=lambda a: a.load_pct, reverse=True)
        return alerts

    def recommend_diversions(
        self,
        G: nx.DiGraph,
        top_n: int = 5,
    ) -> list[dict[str, Any]]:
        """Top-N diversion recommendations for overloaded nodes."""
        alerts = self.congestion_alerts(G)
        result: list[dict[str, Any]] = []

        for alert in alerts[:top_n]:
            div_labels = [
                LOCATION_NODES.get(n, (str(n), "", ""))[0]
                for n in (alert.recommended_diversion or [])
            ]
            result.append(
                {
                    "congested_node": alert.node_id,
                    "congested_name": alert.name,
                    "load_pct": alert.load_pct,
                    "diversion_path": alert.recommended_diversion,
                    "diversion_labels": div_labels,
                }
            )

        return result

    # ── private ──────────────────────────────────────────────────────────
    def _nearest_buffer(
        self,
        G: nx.DiGraph,
        congested_node: int,
    ) -> list[int] | None:
        """Find the nearest P5 buffer node from a congested node."""
        p5_nodes = [
            n for n, d in G.nodes(data=True) if d.get("priority") == "P5"
        ]
        if not p5_nodes:
            return None

        best_path: list[int] | None = None
        best_w = float("inf")

        for p5 in p5_nodes:
            try:
                w = nx.dijkstra_path_length(
                    G, congested_node, p5, weight="weight"
                )
                if w < best_w:
                    best_w = w
                    best_path = nx.dijkstra_path(
                        G, congested_node, p5, weight="weight"
                    )
            except nx.NetworkXNoPath:
                continue

        return best_path
