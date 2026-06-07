"""
FastAPI REST + WebSocket server.

Endpoints
---------
GET  /api/nodes        Fused state of all 25 nodes
GET  /api/graph        Full graph (nodes + edges) as JSON
GET  /api/alerts       Current HIGH / CRITICAL alerts
GET  /api/forecasts    15 / 30-min occupancy forecasts
GET  /api/routes       Safe route between two nodes
GET  /api/diversions   Top-N diversion recommendations
POST /api/scenario     Update scenario / weather at runtime
WS   /ws               Real-time push to connected clients

The web dashboard is served as static files at ``/``.
State is populated by the pipeline via ``update_state()`` and
broadcast to WebSocket clients via ``broadcast()``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import networkx as nx
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from optimization.router import Router

# ── Shared live state (updated by pipeline each tick) ────────────────────
_state: dict[str, Any] = {
    "nodes": {},
    "graph": {"nodes": [], "edges": []},
    "alerts": [],
    "forecasts": {},
    "scenario": "normal_day",
    "weather": "clear",
    "tick": 0,
    "_nx_graph": None,
    "approved_closures": set(),
    "tick_interval": 30,
}

# Webhook payload queue
_ingest_queue: list[dict[str, Any]] = []

# Active WebSocket connections
_connections: set[WebSocket] = set()
_router = Router()


def update_state(new: dict[str, Any]) -> None:
    """Called by the pipeline to push the latest tick state."""
    _state.update(new)


async def broadcast(payload: dict[str, Any]) -> None:
    """Push a JSON payload to every connected WebSocket client."""
    dead: set[WebSocket] = set()
    msg = json.dumps(payload)
    for ws in list(_connections):
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    _connections.difference_update(dead)


def build_ws_payload() -> dict[str, Any]:
    """Build the full state payload for WebSocket broadcast."""
    return {
        "type": "state_update",
        "tick": _state["tick"],
        "scenario": _state["scenario"],
        "weather": _state["weather"],
        "nodes": _state["nodes"],
        "graph": _state["graph"],
        "alerts": _state["alerts"],
        "forecasts": _state["forecasts"],
        "approved_closures": list(_state["approved_closures"]),
        "tick_interval": _state.get("tick_interval", 30),
    }


# ── FastAPI application ───────────────────────────────────────────────────
app = FastAPI(
    title="Simhastha 2028 — Crowd Intelligence API",
    description=(
        "Live crowd flow prediction and route optimization "
        "for Simhastha Ujjain 2028."
    ),
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)


@app.get("/api/nodes")
async def get_nodes() -> JSONResponse:
    """Return current fused state for all 25 location nodes."""
    return JSONResponse(content=list(_state["nodes"].values()))


@app.get("/api/graph")
async def get_graph() -> JSONResponse:
    """Return full live graph (nodes + edges) as JSON."""
    return JSONResponse(content=_state["graph"])


@app.get("/api/alerts")
async def get_alerts() -> JSONResponse:
    """Return all active HIGH / CRITICAL congestion alerts."""
    return JSONResponse(content=_state["alerts"])


@app.get("/api/forecasts")
async def get_forecasts() -> JSONResponse:
    """Return 15-min / 30-min occupancy forecasts for all nodes."""
    return JSONResponse(content=_state["forecasts"])


@app.get("/api/routes")
async def get_route(
    from_node: int = Query(..., alias="from", ge=1, le=25),
    to_node: int = Query(..., alias="to", ge=1, le=25),
) -> JSONResponse:
    """Compute the safest route between two nodes (Dijkstra)."""
    G: nx.DiGraph | None = _state.get("_nx_graph")
    if G is None:
        return JSONResponse(
            status_code=503,
            content={"error": "Graph not ready — try again shortly"},
        )
    result = _router.safe_route(G, from_node, to_node)
    if result is None:
        return JSONResponse(
            status_code=404,
            content={"error": (f"No path from node {from_node} to {to_node}")},
        )
    return JSONResponse(content=result.to_dict())


@app.get("/api/diversions")
async def get_diversions(
    top_n: int = Query(default=5, ge=1, le=10),
) -> JSONResponse:
    """Return top-N diversion recommendations."""
    G: nx.DiGraph | None = _state.get("_nx_graph")
    if G is None:
        return JSONResponse(
            status_code=503,
            content={"error": "Graph not ready — try again shortly"},
        )
    return JSONResponse(content=_router.recommend_diversions(G, top_n=top_n))


class IngestPayload(BaseModel):
    node_id: int
    source_type: str
    estimate: float
    confidence: float


@app.post("/api/ingest")
async def ingest_sensor(payload: IngestPayload) -> JSONResponse:
    """Ingest a real-time sensor reading payload via webhook."""
    _ingest_queue.append(payload.model_dump())
    return JSONResponse(
        content={"status": "queued", "node_id": payload.node_id}
    )


@app.post("/api/scenario")
async def set_scenario(
    scenario: str = Query(
        default="normal_day",
        enum=[
            "normal_day",
            "weekend",
            "parikrama",
            "ekadashi",
            "festival_day",
            "purnima",
            "somvati_amavasya",
            "mahashivratri",
            "shahi_snan",
            "vip_visit",
        ],
    ),
    weather: str = Query(
        default="clear",
        enum=[
            "clear",
            "pleasant",
            "hot_wave",
            "light_rain",
            "heavy_rain",
            "thunderstorm",
        ],
    ),
) -> JSONResponse:
    """Change the active scenario and weather condition."""
    _state["scenario"] = scenario
    _state["weather"] = weather
    return JSONResponse(
        content={
            "status": "updated",
            "scenario": scenario,
            "weather": weather,
        }
    )


@app.post("/api/settings/tick")
async def set_tick_interval(
    interval: int = Query(default=30, ge=1, le=120),
) -> JSONResponse:
    """Dynamically update the pipeline tick interval in seconds."""
    _state["tick_interval"] = interval
    return JSONResponse(
        content={"status": "updated", "tick_interval": interval}
    )


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """Real-time push endpoint for dashboard clients."""
    await ws.accept()
    _connections.add(ws)
    # Send current state immediately on connection
    try:
        await ws.send_text(json.dumps(build_ws_payload()))
        while True:
            data = await ws.receive_json()
            if data.get("action") == "close_gate":
                node_id = data.get("node_id")
                if node_id:
                    _state["approved_closures"].add(node_id)
            elif data.get("action") == "open_gate":
                node_id = data.get("node_id")
                if node_id and node_id in _state["approved_closures"]:
                    _state["approved_closures"].remove(node_id)
    except WebSocketDisconnect:
        pass
    finally:
        _connections.discard(ws)


# ── Static frontend (mount last so API routes take priority) ─────────────
_STATIC = Path(__file__).parent / "static"
if _STATIC.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(_STATIC), html=True),
        name="static",
    )
