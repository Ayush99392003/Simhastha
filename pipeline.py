"""
Main orchestrator for Simhastha Ujjain 2028 Crowd Intelligence.

Runs a continuous pipeline tick:
  1. Polls all dummy providers for signals
  2. Runs the fusion engine to estimate occupancy
  3. Updates short-term EMA predictions
  4. Builds the dynamic NetworkX graph
  5. Computes routing and congestion alerts
  6. Updates the shared API state and displays a Rich terminal dashboard
"""

from __future__ import annotations

import asyncio
import sys
import json
import threading
import time
from pathlib import Path
import threading
import time
from typing import Any

import uvicorn
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from datetime import datetime, timezone

from api.server import app, broadcast, update_state, _state, _ingest_queue
from config.settings import (
    API_HOST,
    API_PORT,
    LOCATION_NODES,
    TICK_INTERVAL_SECONDS,
)
from ingestion.base import CrowdSignal
from fusion.engine import FusionEngine
from graph.state import GraphState
from ingestion.dummy_cctv import DummyCCTVProvider
from ingestion.dummy_gate import DummyGateProvider
from ingestion.dummy_gps import DummyGPSProvider
from ingestion.dummy_qr import DummyQRProvider
from ingestion.dummy_volunteer import DummyVolunteerProvider
from ingestion.dummy_weather import DummyWeatherProvider
from optimization.router import Router
from prediction.forecaster import MLForecaster

# ── Global components ────────────────────────────────────────────────────
console = Console()

providers = [
    DummyGateProvider(seed=42),
    DummyCCTVProvider(seed=42),
    DummyQRProvider(seed=42),
    DummyGPSProvider(seed=42),
    DummyVolunteerProvider(seed=42),
    DummyWeatherProvider(),
]

fusion_engine = FusionEngine()
forecaster = MLForecaster()
graph_state = GraphState()
router = Router()


# ── Rich UI Helpers ──────────────────────────────────────────────────────
def _build_nodes_table() -> Table:
    """Build a Rich table of the current node state."""
    table = Table(
        title="Live Node Occupancy & Risk",
        expand=True,
        header_style="bold blue",
    )
    table.add_column("Node", justify="left")
    table.add_column("Priority", justify="center")
    table.add_column("Occupancy", justify="right")
    table.add_column("Load %", justify="right")
    table.add_column("Risk Level", justify="center")
    table.add_column("Pred (+15m)", justify="right")
    table.add_column("Trend", justify="center")

    # Sort nodes by risk (highest load first)
    nodes_list = list(_state.get("nodes", {}).values())
    nodes_list.sort(key=lambda x: x["load_pct"], reverse=True)

    for node in nodes_list:
        n_id = node["node_id"]
        forecast = _state.get("forecasts", {}).get(n_id, {})
        pred15 = forecast.get("pred_15min", node["fused_occupancy"])
        trend = forecast.get("trend", "stable")

        trend_icon = "➡️"
        if trend == "rising":
            trend_icon = "⬆️"
        elif trend == "falling":
            trend_icon = "⬇️"

        risk = node["risk_level"]
        risk_styled = f"[{node['risk_color']}]{risk}[/]"

        table.add_row(
            str(node["name"]),
            node["priority"],
            f"{int(node['fused_occupancy']):,}",
            f"{node['load_pct']:.1f}%",
            risk_styled,
            f"{int(pred15):,}",
            trend_icon,
        )

    return table


def _build_alerts_panel() -> Panel:
    """Build a Rich panel for active congestion alerts."""
    alerts = _state.get("alerts", [])
    if not alerts:
        return Panel(
            Text("No active alerts. All nodes operating safely.", style="dim"),
            title="Active Alerts",
            border_style="green",
        )

    lines = []
    for alert in alerts:
        color = alert["risk_color"]
        lines.append(
            f"[{color}][bold]{alert['risk_level']}:[/] "
            f"{alert['name']} at {alert['load_pct']:.1f}% load "
            f"({int(alert['fused_occupancy']):,}/{alert['effective_capacity']:,})"
        )

    return Panel("\n".join(lines), title="Active Alerts", border_style="red")


def _build_dashboard() -> Layout:
    """Compose the main Rich layout."""
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main"),
    )
    layout["main"].split_row(
        Layout(name="nodes", ratio=2),
        Layout(name="side", ratio=1),
    )
    layout["side"].split_column(
        Layout(name="alerts", ratio=1),
    )

    # Header
    scenario = _state["scenario"].upper()
    weather = _state["weather"].upper()
    tick = _state["tick"]
    header_text = Text(
        f"Simhastha 2028 | Tick: {tick} | Scenario: {scenario} | Weather: {weather} | API: port {API_PORT}",
        style="bold yellow",
        justify="center",
    )
    layout["header"].update(Panel(header_text))

    # Nodes
    layout["nodes"].update(Panel(_build_nodes_table()))

    # Side
    layout["alerts"].update(_build_alerts_panel())

    return layout


# ── State Persistence ────────────────────────────────────────────────────
STATE_BACKUP_FILE = Path("state_backup.json")


def load_state_from_disk() -> None:
    """Load the shared state and history from disk if available."""
    if STATE_BACKUP_FILE.exists():
        try:
            with open(STATE_BACKUP_FILE, "r") as f:
                data = json.load(f)
            _state["tick"] = data.get("tick", 0)
            _state["scenario"] = data.get("scenario", "normal_day")
            _state["weather"] = data.get("weather", "clear")
            _state["approved_closures"] = set(
                data.get("approved_closures", [])
            )
            if "forecaster" in data:
                forecaster.import_history(data["forecaster"])
            console.print("[green]State restored from disk.[/]")
        except Exception as e:
            console.print(f"[red]Failed to load state backup: {e}[/]")


def save_state_to_disk() -> None:
    """Save the shared state and history to disk."""
    try:
        data = {
            "tick": _state.get("tick", 0),
            "scenario": _state.get("scenario", "normal_day"),
            "weather": _state.get("weather", "clear"),
            "approved_closures": list(_state.get("approved_closures", set())),
            "forecaster": forecaster.export_history(),
        }
        with open(STATE_BACKUP_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        console.print(f"[red]Failed to save state backup: {e}[/]")


# ── Pipeline Loop ────────────────────────────────────────────────────────
def run_tick() -> None:
    """Execute one complete pass of the pipeline."""
    scenario = _state.get("scenario", "normal_day")
    weather = _state.get("weather", "clear")

    # 1. Collect signals
    all_signals = []

    # Drain webhook queue
    while _ingest_queue:
        payload = _ingest_queue.pop(0)
        all_signals.append(
            CrowdSignal(
                node_id=payload["node_id"],
                timestamp=datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                source_type=payload["source_type"],
                estimate=payload["estimate"],
                confidence=payload["confidence"],
                status="ok",
                metadata={"source": "webhook"},
            )
        )

    for provider in providers:
        try:
            signals = provider.emit(scenario=scenario, weather=weather)
            all_signals.extend(signals)
        except Exception as e:
            console.log(
                f"[red]Provider {type(provider).__name__} failed: {e}[/]"
            )

    # 2. Fusion
    fused_states = fusion_engine.fuse(
        all_signals,
        scenario,
        weather,
        approved_closures=_state.get("approved_closures", set()),
    )

    # 3. Prediction
    forecaster.update(fused_states)
    forecasts = forecaster.predict_all(
        fused_states, scenario=scenario, weather=weather
    )

    # 4. Graph update
    G = graph_state.build(
        fused_states,
        forecasts,
        scenario,
        weather,
        approved_closures=_state.get("approved_closures", set()),
    )

    # 5. Routing & Alerts
    alerts = router.congestion_alerts(G)

    # 6. Update shared state
    _state["tick"] += 1
    _state["_nx_graph"] = G

    update_state(
        {
            "nodes": {k: v.to_dict() for k, v in fused_states.items()},
            "forecasts": {k: v.to_dict() for k, v in forecasts.items()},
            "graph": graph_state.to_dict(
                approved_closures=_state.get("approved_closures", set())
            ),
            "alerts": [a.to_dict() for a in alerts],
        }
    )

    if _state["tick"] % 5 == 0:
        save_state_to_disk()


async def _run_api_server() -> None:
    """Run uvicorn in an asyncio task."""
    config = uvicorn.Config(
        app, host=API_HOST, port=API_PORT, log_level="error"
    )
    server = uvicorn.Server(config)
    await server.serve()


def start_api_thread() -> None:
    """Start the FastAPI server in a background thread."""
    loop = asyncio.new_event_loop()
    thread = threading.Thread(
        target=loop.run_until_complete,
        args=(_run_api_server(),),
        daemon=True,
    )
    thread.start()


# ── Main ─────────────────────────────────────────────────────────────────
async def main() -> None:
    # Handle optional command-line overrides
    if "--scenario" in sys.argv:
        idx = sys.argv.index("--scenario")
        if len(sys.argv) > idx + 1:
            _state["scenario"] = sys.argv[idx + 1]

    if "--weather" in sys.argv:
        idx = sys.argv.index("--weather")
        if len(sys.argv) > idx + 1:
            _state["weather"] = sys.argv[idx + 1]

    # Load persisted state
    load_state_from_disk()

    # Start API
    start_api_thread()

    # Pre-warm one tick
    run_tick()

    with Live(_build_dashboard(), refresh_per_second=2, screen=True) as live:
        while True:
            tick_int = _state.get("tick_interval", TICK_INTERVAL_SECONDS)
            elapsed = 0.0

            # Sleep in small chunks so we can broadcast frequently if needed
            while elapsed < tick_int:
                await asyncio.sleep(0.5)
                elapsed += 0.5
                # Ensure websocket clients get live state
                payload = {
                    "type": "state_update",
                    "tick": _state["tick"],
                    "scenario": _state["scenario"],
                    "weather": _state["weather"],
                    "nodes": _state["nodes"],
                    "graph": _state["graph"],
                    "alerts": _state["alerts"],
                    "forecasts": _state["forecasts"],
                    "approved_closures": list(
                        _state.get("approved_closures", set())
                    ),
                    "tick_interval": _state.get("tick_interval", 30),
                }
                await broadcast(payload)

            run_tick()
            live.update(_build_dashboard())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("[yellow]Shutting down...[/]")
        sys.exit(0)
