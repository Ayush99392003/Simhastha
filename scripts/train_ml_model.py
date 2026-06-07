import sys
import os
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor
import pickle

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))


def train_model(
    data_file: str = "training_data.csv",
    model_out: str = "models/forecaster.pkl",
):
    data_path = Path(data_file)
    if not data_path.exists():
        print(f"Data file {data_file} not found.")
        return

    print("Loading training data...")
    df = pd.read_csv(data_path)

    print("Engineering features...")
    df = df.sort_values(["node_id", "tick"])

    # Extract category codes
    df["scenario_cat"] = df["scenario"].astype("category").cat.codes
    df["weather_cat"] = df["weather"].astype("category").cat.codes

    # Create lag features
    for i in range(1, 6):
        df[f"occ_lag_{i}"] = df.groupby("node_id")["fused_occupancy"].shift(i)

    # Create targets (15min = 30 ticks, 30min = 60 ticks)
    df["target_15min"] = df.groupby("node_id")["fused_occupancy"].shift(-30)
    df["target_30min"] = df.groupby("node_id")["fused_occupancy"].shift(-60)

    df = df.dropna()

    features = (
        ["fused_occupancy"]
        + [f"occ_lag_{i}" for i in range(1, 6)]
        + ["scenario_cat", "weather_cat"]
    )
    targets = ["target_15min", "target_30min"]

    X = df[features]
    Y = df[targets]

    print(f"Training Multi-output Random Forest on {len(df)} samples...")
    model = RandomForestRegressor(
        n_estimators=30, max_depth=10, n_jobs=-1, random_state=42
    )
    model.fit(X, Y)

    print("Saving model and label encoders...")
    scenario_mapping = {
        val: i
        for i, val in enumerate(
            df["scenario"].astype("category").cat.categories
        )
    }
    weather_mapping = {
        val: i
        for i, val in enumerate(
            df["weather"].astype("category").cat.categories
        )
    }

    out_path = Path(model_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "wb") as f:
        pickle.dump(
            {
                "model": model,
                "scenario_mapping": scenario_mapping,
                "weather_mapping": weather_mapping,
                "features": features,
            },
            f,
        )

    print(f"Model saved to {model_out}")


if __name__ == "__main__":
    train_model()
