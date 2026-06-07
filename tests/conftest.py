import pytest
from datetime import datetime, timezone
from ingestion.base import CrowdSignal
from config.settings import EVENT_FACTORS


@pytest.fixture
def now():
    return datetime.now(tz=timezone.utc)


@pytest.fixture
def sample_signals(now):
    return [
        CrowdSignal(
            node_id=1,
            timestamp=now,
            source_type="gate",
            estimate=20000,
            confidence=0.9,
        ),
        CrowdSignal(
            node_id=1,
            timestamp=now,
            source_type="cctv",
            estimate=19000,
            confidence=0.8,
        ),
        CrowdSignal(
            node_id=0,
            timestamp=now,
            source_type="weather",
            estimate=0.8,
            confidence=1.0,
        ),
    ]
