
from datetime import datetime


def generate_alerts(rule_results, anomaly_results):

    alerts = []

    for index, rule in enumerate(rule_results, start=1):

        # Collect readings responsible for this alert
        related = anomaly_results[
            anomaly_results["indicator"].isin(
                rule["indicators"]
            )
            & (anomaly_results["anomaly"] == True)
        ]

        readings = []

        for _, row in related.iterrows():
            readings.append({
                "indicator": row["indicator"],
                "current_value": float(row["current_value"]),
                "baseline_mean": float(row["baseline_mean"]),
                "deviation_score": float(row["deviation_score"])
            })

        alert = {
            "alert_id": f"ALT{index:03d}",
            "timestamp": datetime.now().isoformat(
                timespec="seconds"
            ),
            "astronaut_id": (
                anomaly_results["astronaut_id"].iloc[0]
            ),
            "rule": rule["rule"],
            "priority": rule["priority"],
            "indicators": rule["indicators"],
            "explanation": rule["explanation"],
            "readings": readings,
            "recommended_action": (
                "Review the measurements, verify data quality, "
                "and follow the onboard medical procedure."
            ),
            "acknowledged": False
        }

        alerts.append(alert)

    return alerts
