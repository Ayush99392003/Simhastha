from ingestion.dummy_gate import DummyGateProvider
from ingestion.dummy_cctv import DummyCCTVProvider
from ingestion.dummy_qr import DummyQRProvider
from ingestion.dummy_gps import DummyGPSProvider
from ingestion.dummy_weather import DummyWeatherProvider
from ingestion.dummy_volunteer import DummyVolunteerProvider


def test_all_providers_emit_valid_contract():
    providers = [
        DummyGateProvider(),
        DummyCCTVProvider(),
        DummyQRProvider(),
        DummyGPSProvider(),
        DummyVolunteerProvider(),
        DummyWeatherProvider(),
    ]

    for provider in providers:
        signals = provider.emit()
        assert isinstance(signals, list)
        for sig in signals:
            assert hasattr(sig, "node_id")
            assert hasattr(sig, "source_type")
            assert 0.0 <= sig.confidence <= 1.0
