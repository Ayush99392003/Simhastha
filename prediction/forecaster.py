"""
Short-term crowd forecaster using Exponential Moving Average (EMA).

Maintains a rolling per-node occupancy history and produces:
    pred_15min  — expected occupancy 15 minutes ahead
    pred_30min  — expected occupancy 30 minutes ahead
    trend       — "rising" | "stable" | "falling"

Method
------
1. After each tick the EMA is updated:
       ema_t = α × occ_t + (1 − α) × ema_{t-1}   (α = EMA_ALPHA)

2. The short-term slope is estimated from the last N ticks of
   raw occupancy history:
       slope = (occ_last − occ_first) / (N − 1)   [people / tick]

3. Linear extrapolation from the EMA:
       pred_k = ema + slope × k_ticks
   where k_ticks = 30 for 15-min and 60 for 30-min
   (each tick = TICK_INTERVAL_SECONDS seconds).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

import pickle
import numpy as np
from pathlib import Path

from config.settings import EMA_ALPHA, HISTORY_WINDOW
from fusion.engine import FusedNodeState


@dataclass
class NodeForecast:
    """Prediction output for a single location node."""

    node_id: int
    current: float
    pred_15min: float
    pred_30min: float
    trend: str  # "rising" | "stable" | "falling"

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "current": round(self.current),
            "pred_15min": round(self.pred_15min),
            "pred_30min": round(self.pred_30min),
            "trend": self.trend,
        }


class Forecaster:
    """
    EMA-based short-term occupancy forecaster.
    Call ``update()`` once per pipeline tick, then ``predict_all()``.
    """

    def __init__(self) -> None:
        self._ema: dict[int, float] = {}
        self._history: dict[int, deque[float]] = {}

    # ── public API ────────────────────────────────────────────────────────
    def update(
        self,
        fused_states: dict[int, FusedNodeState],
    ) -> None:
        """Ingest latest fused occupancies and update EMAs."""
        for node_id, state in fused_states.items():
            occ = state.fused_occupancy
            if node_id not in self._ema:
                self._ema[node_id] = occ
                self._history[node_id] = deque(maxlen=HISTORY_WINDOW)
            else:
                self._ema[node_id] = (
                    EMA_ALPHA * occ + (1 - EMA_ALPHA) * self._ema[node_id]
                )
            self._history[node_id].append(occ)

    def predict(
        self, node_id: int, effective_capacity: int = 1000000
    ) -> NodeForecast | None:
        """Return a ``NodeForecast`` for a single node, or None."""
        if node_id not in self._ema:
            return None

        ema_val = self._ema[node_id]
        history = list(self._history[node_id])

        if len(history) < 2:
            return NodeForecast(
                node_id=node_id,
                current=ema_val,
                pred_15min=ema_val,
                pred_30min=ema_val,
                trend="stable",
            )

        # Slope over last ≤5 ticks (people per tick)
        window = history[-min(5, len(history)) :]
        slope = (window[-1] - window[0]) / max(len(window) - 1, 1)

        # 1 tick ≈ 30 s  →  15 min = 30 ticks, 30 min = 60 ticks
        pred_15 = max(0.0, min(ema_val + slope * 30, effective_capacity))
        pred_30 = max(0.0, min(ema_val + slope * 60, effective_capacity))

        # Trend: >1 % of EMA per tick = meaningful change
        threshold = ema_val * 0.01
        if slope > threshold:
            trend = "rising"
        elif slope < -threshold:
            trend = "falling"
        else:
            trend = "stable"

        return NodeForecast(
            node_id=node_id,
            current=ema_val,
            pred_15min=pred_15,
            pred_30min=pred_30,
            trend=trend,
        )

    def predict_all(
        self,
        fused_states: dict[int, FusedNodeState],
    ) -> dict[int, NodeForecast]:
        """Return forecasts for every node in ``fused_states``."""
        result: dict[int, NodeForecast] = {}
        for nid, state in fused_states.items():
            fc = self.predict(nid, state.effective_capacity)
            if fc is not None:
                result[nid] = fc
        return result

    def export_history(self) -> dict[str, Any]:
        """Export EMA and history for persistence."""
        return {
            "ema": self._ema,
            "history": {str(k): list(v) for k, v in self._history.items()},
        }

    def import_history(self, data: dict[str, Any]) -> None:
        """Import EMA and history from persistence."""
        self._ema = {int(k): v for k, v in data.get("ema", {}).items()}
        self._history = {
            int(k): deque(v, maxlen=HISTORY_WINDOW)
            for k, v in data.get("history", {}).items()
        }


class MLForecaster(Forecaster):
    """
    ML-based forecaster using RandomForestRegressor.
    Falls back to Forecaster (EMA) if the model is not found or fails.
    """

    def __init__(self, model_path: str = "models/forecaster.pkl") -> None:
        super().__init__()
        self.use_ml = False
        self.model = None
        self.scenario_mapping: dict[str, int] = {}
        self.weather_mapping: dict[str, int] = {}

        path = Path(model_path)
        if path.exists():
            try:
                with open(path, "rb") as f:
                    data = pickle.load(f)
                self.model = data["model"]
                self.scenario_mapping = data["scenario_mapping"]
                self.weather_mapping = data["weather_mapping"]
                self.use_ml = True
                print(
                    f"MLForecaster: Successfully loaded ML model from {model_path}"
                )
            except Exception as e:
                print(
                    f"MLForecaster: Failed to load model from {model_path}: {e}"
                )
        else:
            print(
                f"MLForecaster: Model not found at {model_path}, falling back to EMA."
            )

    def predict(
        self,
        node_id: int,
        effective_capacity: int = 1000000,
        scenario: str = "normal_day",
        weather: str = "clear",
    ) -> NodeForecast | None:
        """Return an ML-based NodeForecast, or fallback to EMA."""
        if not self.use_ml:
            return super().predict(node_id, effective_capacity)

        if node_id not in self._ema:
            return None

        history = list(self._history[node_id])
        if len(history) < 6:  # We need current + 5 lags = 6
            return super().predict(node_id, effective_capacity)

        recent = history[-6:]
        current_occ = recent[-1]
        lag_1 = recent[-2]
        lag_2 = recent[-3]
        lag_3 = recent[-4]
        lag_4 = recent[-5]
        lag_5 = recent[-6]

        scenario_cat = self.scenario_mapping.get(scenario, 0)
        weather_cat = self.weather_mapping.get(weather, 0)

        X = np.array(
            [
                [
                    current_occ,
                    lag_1,
                    lag_2,
                    lag_3,
                    lag_4,
                    lag_5,
                    scenario_cat,
                    weather_cat,
                ]
            ]
        )

        try:
            import warnings

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                preds = self.model.predict(X)[
                    0
                ]  # [target_15min, target_30min]
            pred_15 = float(max(0.0, min(preds[0], effective_capacity)))
            pred_30 = float(max(0.0, min(preds[1], effective_capacity)))

            # Estimate trend based on predicted vs current
            if pred_15 > current_occ * 1.05:
                trend = "rising"
            elif pred_15 < current_occ * 0.95:
                trend = "falling"
            else:
                trend = "stable"

            return NodeForecast(
                node_id=node_id,
                current=current_occ,
                pred_15min=pred_15,
                pred_30min=pred_30,
                trend=trend,
            )
        except Exception:
            return super().predict(node_id, effective_capacity)

    def predict_all(
        self,
        fused_states: dict[int, FusedNodeState],
        scenario: str = "normal_day",
        weather: str = "clear",
    ) -> dict[int, NodeForecast]:
        """Return ML forecasts for every node in ``fused_states``."""
        result: dict[int, NodeForecast] = {}
        for nid, state in fused_states.items():
            if self.use_ml:
                fc = self.predict(
                    nid, state.effective_capacity, scenario, weather
                )
            else:
                fc = super().predict(nid, state.effective_capacity)

            if fc is not None:
                result[nid] = fc
        return result
