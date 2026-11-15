"""Explainable, per-astronaut multi-indicator rule engine."""
import pandas as pd


def evaluate_health_patterns(anomaly_results):
    alerts = []
    if anomaly_results is None or anomaly_results.empty:
        return alerts
    abnormal = anomaly_results[anomaly_results["anomaly"].fillna(False).astype(bool)]
    if abnormal.empty:
        return alerts

    rules = [
        ("HEART_RATE_DEVIATION", {"heart_rate"}, "attention",
         "Heart rate differs significantly from the astronaut's personal baseline."),
        ("SPO2_DEVIATION", {"spo2"}, "attention",
         "Oxygen saturation differs significantly from the astronaut's personal baseline."),
        ("TEMPERATURE_DEVIATION", {"temperature"}, "attention",
         "Body temperature differs significantly from the astronaut's personal baseline."),
        ("SLEEP_FATIGUE_PATTERN", {"sleep_duration", "fatigue"}, "attention",
         "Unusual sleep duration and fatigue changes were detected together."),
    ]
    for aid, crew_rows in abnormal.groupby("astronaut_id", dropna=False):
        indicators = set(crew_rows["indicator"].astype(str))
        for name, required, priority, explanation in rules:
            if required.issubset(indicators):
                alerts.append({
                    "astronaut_id": aid, "rule": name, "priority": priority,
                    "indicators": sorted(required), "explanation": explanation,
                })
        if len(indicators) >= 3:
            alerts.append({
                "astronaut_id": aid, "rule": "MULTI_INDICATOR_DEVIATION",
                "priority": "review", "indicators": sorted(indicators),
                "explanation": "Multiple health indicators differ from the astronaut's personal baseline.",
            })
    return alerts
