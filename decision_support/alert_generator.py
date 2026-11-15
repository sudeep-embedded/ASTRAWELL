"""Deterministic, astronaut-scoped alert generation."""
from datetime import datetime
import hashlib
import pandas as pd


def generate_alerts(rule_results, anomaly_results):
    alerts = []
    if anomaly_results is None or anomaly_results.empty:
        return alerts
    for rule in rule_results or []:
        aid = rule.get("astronaut_id")
        related = anomaly_results[
            anomaly_results["indicator"].isin(rule["indicators"])
            & anomaly_results["anomaly"].fillna(False).astype(bool)
        ]
        if aid is not None:
            related = related[related["astronaut_id"] == aid]
        if related.empty:
            continue
        if aid is None:
            aid = related["astronaut_id"].iloc[0]
        readings = []
        for _, row in related.iterrows():
            readings.append({
                "indicator": row["indicator"],
                "current_value": float(row["current_value"]),
                "baseline_mean": float(row["baseline_mean"]),
                "deviation_score": float(row["deviation_score"]),
                "signed_z_score": float(row.get("signed_z_score", row["deviation_score"])),
            })
        source_ts = related["timestamp"].max()
        try:
            timestamp = pd.Timestamp(source_ts).isoformat(timespec="seconds")
        except Exception:
            timestamp = datetime.utcnow().isoformat(timespec="seconds")
        identity = f"{aid}|{rule['rule']}|{timestamp}|{','.join(sorted(rule['indicators']))}"
        alert_id = "ALT-" + hashlib.sha1(identity.encode()).hexdigest()[:10].upper()
        alerts.append({
            "alert_id": alert_id, "timestamp": timestamp, "astronaut_id": aid,
            "rule": rule["rule"], "priority": rule["priority"],
            "indicators": rule["indicators"], "explanation": rule["explanation"],
            "readings": readings,
            "recommended_action": "Review the measurements, verify data quality, and follow the approved onboard medical procedure.",
            "acknowledged": False,
        })
    return alerts
