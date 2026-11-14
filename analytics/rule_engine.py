"""Explainable rule engine — implementation comes later."""

def evaluate_health_patterns(anomaly_results):

    alerts = []

    # Extract detected anomalies
    abnormal = anomaly_results[
        anomaly_results["anomaly"] == True
    ]

    indicators = set(abnormal["indicator"])

    # Rule 1: Heart rate deviation
    if "heart_rate" in indicators:

        alerts.append({
            "rule": "HEART_RATE_DEVIATION",
            "priority": "attention",
            "indicators": ["heart_rate"],
            "explanation": (
                "Heart rate differs significantly "
                "from the astronaut's personal baseline."
            )
        })

    # Rule 2: Oxygen saturation deviation
    if "spo2" in indicators:

        alerts.append({
            "rule": "SPO2_DEVIATION",
            "priority": "attention",
            "indicators": ["spo2"],
            "explanation": (
                "Blood oxygen saturation differs "
                "significantly from the personal baseline."
            )
        })

    # Rule 3: Temperature deviation
    if "temperature" in indicators:

        alerts.append({
            "rule": "TEMPERATURE_DEVIATION",
            "priority": "attention",
            "indicators": ["temperature"],
            "explanation": (
                "Body temperature differs significantly "
                "from the personal baseline."
            )
        })

    # Rule 4: Sleep and fatigue combination
    if (
        "sleep_duration" in indicators
        and "fatigue" in indicators
    ):

        alerts.append({
            "rule": "SLEEP_FATIGUE_PATTERN",
            "priority": "attention",
            "indicators": [
                "sleep_duration",
                "fatigue"
            ],
            "explanation": (
                "Unusual sleep duration and fatigue "
                "changes were detected together."
            )
        })

    # Rule 5: Multiple indicator deviations
    if len(indicators) >= 3:

        alerts.append({
            "rule": "MULTI_INDICATOR_DEVIATION",
            "priority": "review",
            "indicators": sorted(indicators),
            "explanation": (
                "Multiple health indicators differ "
                "from the astronaut's personal baseline."
            )
        })

    return alerts
