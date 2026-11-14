
import pandas as pd


def detect_anomalies(df, baseline):

    results = []

    for _, reading in df.iterrows():

        astronaut_id = reading["astronaut_id"]
        indicator = reading["indicator"]
        value = reading["value"]

        matching = baseline[
            (baseline["astronaut_id"] == astronaut_id) &
            (baseline["indicator"] == indicator)
        ]

        if matching.empty:
            continue

        reference = matching.iloc[0]

        mean = reference["mean"]
        std = reference["std"]

        # Avoid division by zero
        if std == 0:
            deviation_score = 0 if value == mean else float("inf")
        else:
            deviation_score = abs(value - mean) / std

        # Flag readings more than 2 standard deviations away
        is_anomaly = deviation_score > 2

        results.append({
            "astronaut_id": astronaut_id,
            "timestamp": reading["timestamp"],
            "indicator": indicator,
            "current_value": value,
            "baseline_mean": mean,
            "deviation_score": deviation_score,
            "anomaly": is_anomaly
        })

    return pd.DataFrame(results)
