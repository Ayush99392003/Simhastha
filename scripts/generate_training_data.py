import sys
import os
import random
import csv
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.settings import EVENT_FACTORS, WEATHER_FACTORS
from ingestion.dummy_cctv import DummyCCTVProvider
from ingestion.dummy_gate import DummyGateProvider
from ingestion.dummy_gps import DummyGPSProvider
from ingestion.dummy_qr import DummyQRProvider
from ingestion.dummy_volunteer import DummyVolunteerProvider
from ingestion.dummy_weather import DummyWeatherProvider
from fusion.engine import FusionEngine


def generate_data(
    num_ticks: int = 15000, output_file: str = "training_data.csv"
):
    providers = [
        DummyGateProvider(seed=42),
        DummyCCTVProvider(seed=42),
        DummyQRProvider(seed=42),
        DummyGPSProvider(seed=42),
        DummyVolunteerProvider(seed=42),
        DummyWeatherProvider(),
    ]

    fusion_engine = FusionEngine()

    scenarios = list(EVENT_FACTORS.keys())
    weathers = list(WEATHER_FACTORS.keys())

    current_scenario = "normal_day"
    current_weather = "clear"

    output_path = Path(output_file)
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["tick", "node_id", "scenario", "weather", "fused_occupancy"]
        )

        for tick in range(num_ticks):
            if tick % 1000 == 0:
                print(f"Generating tick {tick}/{num_ticks}...")

            if random.random() < 0.005:
                current_scenario = random.choice(scenarios)
            if random.random() < 0.01:
                current_weather = random.choice(weathers)

            all_signals = []
            for provider in providers:
                try:
                    signals = provider.emit(
                        scenario=current_scenario, weather=current_weather
                    )
                    all_signals.extend(signals)
                except Exception as e:
                    print(f"Provider error: {e}")

            fused_states = fusion_engine.fuse(
                all_signals,
                current_scenario,
                current_weather,
                approved_closures=set(),
            )

            for node_id, state in fused_states.items():
                writer.writerow(
                    [
                        tick,
                        node_id,
                        current_scenario,
                        current_weather,
                        round(state.fused_occupancy, 2),
                    ]
                )

    print(
        f"Successfully generated {num_ticks} ticks of data into {output_file}"
    )


if __name__ == "__main__":
    generate_data()
