
import pandas as pd


def normalize_health_data(df):

    df = df.copy()

    # 1. Remove unnecessary whitespace
    string_columns = [
        "astronaut_id",
        "indicator",
        "unit",
        "source"
    ]

    for column in string_columns:
        df[column] = df[column].astype("string").str.strip()

    # 2. Standardize indicator names
    df["indicator"] = df["indicator"].str.lower()

    # 3. Standardize source names
    df["source"] = df["source"].str.lower()

    # 4. Convert timestamps
    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce"
    )

    # 5. Convert measurements to numeric values
    df["value"] = pd.to_numeric(
        df["value"],
        errors="coerce"
    )

    # 6. Reset row indexes
    df = df.reset_index(drop=True)

    return df
