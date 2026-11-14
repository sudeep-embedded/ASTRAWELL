
from ingestion.csv_loader import load_health_data
from preprocessing.normalizer import normalize_health_data
from analytics.baseline import calculate_baseline
from analytics.anomaly_detector import detect_anomalies

# Load historical data
data = load_health_data(
    "data/sample/health_readings.csv"
)

data = normalize_health_data(data)

# Calculate historical baseline
baseline = calculate_baseline(data)

# Simulated new readings
new_readings = data.iloc[:5].copy()

new_readings["timestamp"] = "2026-11-14 16:00:00"

new_readings["value"] = [
    95.0,   # Heart rate
    98.0,   # SpO2
    36.8,   # Temperature
    7.2,    # Sleep
    2.0     # Fatigue
]

# Detect anomalies
results = detect_anomalies(new_readings, baseline)

print("\nASTRAWELL NEW READING ANALYSIS")
print("--------------------------------")

print(results.to_string(index=False))

print("\nTotal anomalies:", results["anomaly"].sum())
