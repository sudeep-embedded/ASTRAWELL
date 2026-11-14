
from ingestion.csv_loader import load_health_data
from preprocessing.normalizer import normalize_health_data

file_path = "data/sample/health_readings.csv"

# Load original data
data = load_health_data(file_path)

# Normalize data
normalized_data = normalize_health_data(data)

print("\nASTRAWELL DATA NORMALIZATION")
print("----------------------------")

print("Total records:", len(normalized_data))

print("\nNormalized data:")
print(normalized_data)

print("\nData types:")
print(normalized_data.dtypes)
