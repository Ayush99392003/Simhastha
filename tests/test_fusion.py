import pytest

from fusion.engine import FusionEngine
from config.settings import FUSION_WEIGHTS


def test_fusion_weights_sum():
    assert sum(FUSION_WEIGHTS.values()) == pytest.approx(1.0)


def test_fusion_engine(sample_signals):
    engine = FusionEngine()
    result = engine.fuse(
        sample_signals, scenario="normal_day", weather="light_rain"
    )

    # Node 1 should be present
    assert 1 in result
    state = result[1]

    # Should calculate risk and capacity
    assert state.effective_capacity > 0
    assert state.safe_threshold > 0
    assert state.fused_occupancy > 0
    assert state.risk_level in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
