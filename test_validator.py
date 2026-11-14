from ingestion.csv_loader import load_health_data
from preprocessing.validator import validate_health_data

file_path = "data/sample/health_readings.csv"

data = load_health_data(file_path)

result = validate_health_data(data)

print("\nASTRAWELL DATA VALIDATION")
print("------------------------")

print("Valid:", result["valid"])
print("Total records:", result["total_records"])

print("\nErrors:")
for error in result["errors"]:
    print("-", error)

print("\nWarnings:")
for warning in result["warnings"]:
    print("-", warning)