"""Alert explanations — implementation comes later."""

def explain_alert(alert):

    explanations = []

    for reading in alert["readings"]:

        indicator = reading["indicator"]
        current = reading["current_value"]
        baseline = reading["baseline_mean"]
        deviation = reading["deviation_score"]

        explanations.append({
            "indicator": indicator,
            "current_value": current,
            "baseline_value": baseline,
            "difference": round(current - baseline, 2),
            "deviation_score": round(deviation, 2),
            "message": (
                f"{indicator.replace('_', ' ').title()} "
                f"changed from baseline {baseline} "
                f"to current value {current}."
            )
        })

    return {
        "alert_id": alert["alert_id"],
        "priority": alert["priority"],
        "summary": alert["explanation"],
        "details": explanations,
        "recommended_action": alert["recommended_action"]
    }
