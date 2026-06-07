from prediction.forecaster import Forecaster
from fusion.engine import FusedNodeState


def test_forecaster_trend():
    forecaster = Forecaster()

    # Tick 1
    forecaster.update(
        {
            1: FusedNodeState(
                1,
                "Ram Ghat",
                "P1",
                "#FFF",
                10000,
                20000,
                16000,
                "LOW",
                "#000",
                50.0,
            )
        }
    )
    assert forecaster.predict(1).trend == "stable"

    # Tick 2
    forecaster.update(
        {
            1: FusedNodeState(
                1,
                "Ram Ghat",
                "P1",
                "#FFF",
                12000,
                20000,
                16000,
                "LOW",
                "#000",
                60.0,
            )
        }
    )
    fc = forecaster.predict(1)

    # Since occupancy increased, EMA goes up and slope is positive
    assert fc.trend == "rising"
    assert fc.pred_15min > fc.current
