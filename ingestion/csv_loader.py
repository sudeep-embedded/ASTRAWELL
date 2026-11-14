import pandas as pd
from pathlib import Path


def load_health_data(file_path):
    """
    Load astronaut health readings from a CSV file.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    df = pd.read_csv(path)

    required_columns = [
        "astronaut_id",
        "timestamp",
        "indicator",
        "value",
        "unit",
        "source"
    ]

    missing = set(required_columns) - set(df.columns)

    if missing:
        raise ValueError(f"Missing columns: {missing}")

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce"
    )

    df["value"] = pd.to_numeric(
        df["value"],
        errors="coerce"
    )

    return df