
import pandas as pd

VALID_INDICATORS = {
    "heart_rate": {
        "unit": "bpm",
        "min": 1,
        "max": 250
    },
    "spo2": {
        "unit": "percent",
        "min": 0,
        "max": 100
    },
    "temperature": {
        "unit": "C",
        "min": 25,
        "max": 45
    },
    "sleep_duration": {
        "unit": "hours",
        "min": 0,
        "max": 24
    },
    "fatigue": {
        "unit": "score",
        "min": 1,
        "max": 5
    }
}


def validate_health_data(df):

    required_columns = [
        "astronaut_id",
        "timestamp",
        "indicator",
        "value",
        "unit",
        "source"
    ]

    errors = []
    warnings = []

    missing_columns = set(required_columns) - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing columns: {missing_columns}"
        )

    df = df.copy()

    # 1. Check missing values
    for column in required_columns:
        count = df[column].isna().sum()

        if count > 0:
            warnings.append(
                f"{count} missing values in {column}"
            )

    # 2. Check indicator names
    invalid_indicators = ~df["indicator"].isin(
        VALID_INDICATORS
    )

    if invalid_indicators.any():
        errors.append(
            "Unknown health indicators detected"
        )

    # 3. Check numeric measurements
    numeric_values = pd.to_numeric(
        df["value"],
        errors="coerce"
    )

    invalid_numeric = numeric_values.isna()

    if invalid_numeric.any():
        errors.append(
            f"{invalid_numeric.sum()} invalid numeric values"
        )

    # 4. Check timestamps
    timestamps = pd.to_datetime(
        df["timestamp"],
        errors="coerce"
    )

    if timestamps.isna().any():
        errors.append(
            "Invalid or missing timestamps detected"
        )

    # 5. Check units and measurement ranges
    for index, row in df.iterrows():

        indicator = row["indicator"]

        if indicator not in VALID_INDICATORS:
            continue

        config = VALID_INDICATORS[indicator]

        if row["unit"] != config["unit"]:
            errors.append(
                f"Row {index}: Incorrect unit for {indicator}"
            )
            continue

        value = numeric_values.loc[index]

        if pd.isna(value):
            continue

        if not config["min"] <= value <= config["max"]:
            errors.append(
                f"Row {index}: {indicator} value "
                f"{value} is outside allowed input range "
                f"({config['min']}–{config['max']})"
            )

    # 6. Check duplicate records
    duplicates = df.duplicated(
        subset=[
            "astronaut_id",
            "timestamp",
            "indicator"
        ]
    )

    if duplicates.any():
        warnings.append(
            f"{duplicates.sum()} duplicate records detected"
        )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "total_records": len(df)
    }
