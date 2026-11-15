"""JSON ingestion for normalized long-format health readings."""
from pathlib import Path
import json
import pandas as pd

REQUIRED_COLUMNS = ["astronaut_id", "timestamp", "indicator", "value", "unit", "source"]


def load_health_data_json(file_path):
    """Load a JSON array/object or newline-delimited JSON into a DataFrame."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    try:
        if path.suffix.lower() in {".jsonl", ".ndjson"}:
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            df = pd.DataFrame(records)
        else:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                payload = payload.get("readings", [payload])
            if not isinstance(payload, list):
                raise ValueError("JSON must contain an array of readings or an object with a 'readings' array")
            df = pd.DataFrame(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc
    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    df = df[REQUIRED_COLUMNS].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df
