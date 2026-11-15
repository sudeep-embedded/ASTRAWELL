"""Baseline-relative anomaly scoring."""
import numpy as np
import pandas as pd


def detect_anomalies(df, baseline, threshold=2.0, minimum_std=1e-9):
    """Score each reading against its own astronaut/indicator baseline.

    deviation_score is absolute z-score for backward compatibility; signed_z_score
    preserves direction. Baselines with fewer than two observations are not scored.
    """
    required = {"astronaut_id", "indicator", "value"}
    if required - set(df.columns) or {"astronaut_id", "indicator", "mean", "std", "count"} - set(baseline.columns):
        raise ValueError("Readings/baseline are missing required columns")
    lookup = baseline.set_index(["astronaut_id", "indicator"])
    rows = []
    for _, reading in df.iterrows():
        key = (reading["astronaut_id"], reading["indicator"])
        if key not in lookup.index:
            continue
        ref = lookup.loc[key]
        if isinstance(ref, pd.DataFrame):
            ref = ref.iloc[0]
        value = pd.to_numeric(pd.Series([reading["value"]]), errors="coerce").iloc[0]
        if pd.isna(value) or int(ref["count"]) < 2:
            continue
        mean, std = float(ref["mean"]), float(ref["std"])
        signed = (float(value) - mean) / max(std, minimum_std)
        score = abs(signed)
        row = {
            "astronaut_id": reading["astronaut_id"],
            "timestamp": reading.get("timestamp", reading.get("ts")),
            "indicator": reading["indicator"],
            "current_value": float(value),
            "baseline_mean": mean,
            "baseline_count": int(ref["count"]),
            "signed_z_score": signed,
            "deviation_score": score,
            "anomaly": bool(score > threshold),
        }
        rows.append(row)
    return pd.DataFrame(rows, columns=[
        "astronaut_id", "timestamp", "indicator", "current_value",
        "baseline_mean", "baseline_count", "signed_z_score",
        "deviation_score", "anomaly"
    ])
