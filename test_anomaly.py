
from ingestion.csv_loader import load_health_data
from preprocessing.validator import validate_health_data
from preprocessing.normalizer import normalize_health_data
from analytics.baseline import calculate_baseline
from analytics.anomaly_detector import detect_anomalies

# Load data
data = load_health_data(
    "data/sample/health_readings.csv"
)

# Validate
validation = validate_health_data(data)

if not validation["valid"]:
    print(validation["errors"])
    raise SystemExit(1)

# Normalize
data = normalize_health_data(data)

# Calculate baseline
baseline = calculate_baseline(data)

# Detect anomalies
results = detect_anomalies(data, baseline)

print("\nASTRAWELL ANOMALY DETECTION")
print("---------------------------")

print(results.to_string(index=False))

print("\nTotal anomalies:", results["anomaly"].sum())
