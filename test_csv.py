from ingestion.csv_loader import load_health_data

file_path = "data/sample/health_readings.csv"

data = load_health_data(file_path)

print(data)
print("\nTotal records:", len(data))
print("\nIndicators:", data["indicator"].unique())