
from ingestion.csv_loader import load_health_data
from preprocessing.validator import validate_health_data
from preprocessing.normalizer import normalize_health_data
from analytics.baseline import (
    calculate_baseline,
    get_astronaut_baseline
)

# Load data
data = load_health_data(
    "data/sample/health_readings.csv"
)

# Validate data
validation = validate_health_data(data)

if not validation["valid"]:
    print("Invalid data:", validation["errors"])
    raise SystemExit(1)

# Normalize data
data = normalize_health_data(data)

# Calculate baseline
baseline = calculate_baseline(data)

print("\nASTRAWELL PERSONAL HEALTH BASELINE")
print("---------------------------------")

print(baseline.to_string(index=False))

print("\nASTRONAUT AST001 BASELINE")
print("---------------------------------")

print(
    get_astronaut_baseline(
        baseline,
        "AST001"
    ).to_string(index=False)
)
