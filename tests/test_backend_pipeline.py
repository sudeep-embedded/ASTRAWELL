import pandas as pd

from analytics.baseline import calculate_baseline
from analytics.anomaly_detector import detect_anomalies
from analytics.rule_engine import evaluate_health_patterns
from decision_support.alert_generator import generate_alerts


def test_alerts_are_scoped_to_each_astronaut_and_deterministic():
    historical = pd.DataFrame([
        {"astronaut_id": aid, "indicator": ind, "value": value}
        for aid, base in [("A1", 60), ("A2", 70)]
        for ind, value in [
            ("heart_rate", base), ("spo2", 98), ("temperature", 36.5),
            ("sleep_duration", 7), ("fatigue", 2),
        ]
        for _ in range(6)
    ])
    baseline = calculate_baseline(historical)
    new = pd.DataFrame([
        {"astronaut_id": "A1", "indicator": "heart_rate", "value": 95, "timestamp": "2026-11-15T10:00:00Z"},
        {"astronaut_id": "A2", "indicator": "heart_rate", "value": 70, "timestamp": "2026-11-15T10:00:00Z"},
        {"astronaut_id": "A2", "indicator": "spo2", "value": 80, "timestamp": "2026-11-15T10:00:00Z"},
        {"astronaut_id": "A2", "indicator": "temperature", "value": 39, "timestamp": "2026-11-15T10:00:00Z"},
    ])
    anomalies = detect_anomalies(new, baseline, threshold=2.0)
    assert set(anomalies.loc[anomalies["anomaly"], "astronaut_id"]) == {"A1", "A2"}
    rules = evaluate_health_patterns(anomalies)
    alerts = generate_alerts(rules, anomalies)
    assert {a["astronaut_id"] for a in alerts} == {"A1", "A2"}
    assert len({a["alert_id"] for a in alerts}) == len(alerts)
    assert alerts == generate_alerts(rules, anomalies)


def test_baseline_handles_single_reading_without_nan_std():
    df = pd.DataFrame([{"astronaut_id": "A1", "indicator": "heart_rate", "value": 70}])
    result = calculate_baseline(df)
    assert result.loc[0, "std"] == 0
    assert result.loc[0, "count"] == 1
