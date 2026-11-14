
from ingestion.csv_loader import load_health_data
from preprocessing.normalizer import normalize_health_data
from analytics.baseline import calculate_baseline
from analytics.anomaly_detector import detect_anomalies
from analytics.rule_engine import evaluate_health_patterns
from decision_support.alert_generator import generate_alerts

# Load historical data
data = load_health_data(
    "data/sample/health_readings.csv"
)

data = normalize_health_data(data)

# Calculate baseline
baseline = calculate_baseline(data)

# Simulate new readings
new_readings = data.iloc[:5].copy()

new_readings["timestamp"] = "2026-11-14 16:00:00"

new_readings["value"] = [
    95.0,
    98.0,
    36.8,
    7.2,
    4.0
]

# Detect anomalies
anomalies = detect_anomalies(
    new_readings,
    baseline
)

# Evaluate rules
rules = evaluate_health_patterns(anomalies)

# Generate alerts
alerts = generate_alerts(rules, anomalies)

print("\nASTRAWELL ALERT GENERATOR")
print("-------------------------")

for alert in alerts:
    print("\nAlert ID:", alert["alert_id"])
    print("Priority:", alert["priority"])
    print("Rule:", alert["rule"])
    print("Explanation:", alert["explanation"])
    print("Readings:", alert["readings"])
    print("Acknowledged:", alert["acknowledged"])

print("\nTotal alerts:", len(alerts))
