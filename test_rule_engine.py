
from ingestion.csv_loader import load_health_data
from preprocessing.normalizer import normalize_health_data
from analytics.baseline import calculate_baseline
from analytics.anomaly_detector import detect_anomalies
from analytics.rule_engine import evaluate_health_patterns

# Load historical data
data = load_health_data(
    "data/sample/health_readings.csv"
)

data = normalize_health_data(data)

# Calculate baseline
baseline = calculate_baseline(data)

# Simulated new measurements
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

# Evaluate combined patterns
alerts = evaluate_health_patterns(anomalies)

print("\nASTRAWELL RULE ENGINE")
print("---------------------")

for alert in alerts:
    print("\nRule:", alert["rule"])
    print("Priority:", alert["priority"])
    print("Indicators:", alert["indicators"])
    print("Explanation:", alert["explanation"])

print("\nTotal alerts:", len(alerts))
