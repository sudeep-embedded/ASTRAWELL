"""CSV ingestion helpers for ASTRAWELL long- and wide-format telemetry."""
from __future__ import annotations

import pandas as pd

WIDE_COLUMNS = {
    "heart_rate_bpm": ("heart_rate", "bpm"),
    "spo2_percent": ("spo2", "percent"),
    "temperature_C": ("temperature", "C"),
    "sleep_duration_hours": ("sleep_duration", "hours"),
    "fatigue_score": ("fatigue", "score"),
}
LONG_COLUMNS = {"astronaut_id", "timestamp", "indicator", "value", "unit"}


def prepare_telemetry_csv(frame: pd.DataFrame) -> pd.DataFrame:
    """Return canonical long format; reject unknown or incomplete schemas explicitly."""
    data = frame.copy()
    data.columns = [str(column).strip() for column in data.columns]
    if LONG_COLUMNS.issubset(data.columns):
        if "source" not in data.columns:
            data["source"] = "csv_import"
        return data[["astronaut_id", "timestamp", "indicator", "value", "unit", "source"]]

    required_wide = {"astronaut_id", "timestamp"}
    present_wide = required_wide | (set(data.columns) & set(WIDE_COLUMNS))
    if not required_wide.issubset(data.columns):
        missing = sorted(required_wide - set(data.columns))
        raise ValueError(f"Unsupported CSV schema. Missing required identity columns: {missing}")
    measurement_columns = [column for column in WIDE_COLUMNS if column in data.columns]
    if not measurement_columns:
        raise ValueError(
            "Unsupported CSV schema. Expected long format "
            "(astronaut_id,timestamp,indicator,value,unit) or wide format with "
            "heart_rate_bpm, spo2_percent, temperature_C, sleep_duration_hours, fatigue_score."
        )

    wide = data[["astronaut_id", "timestamp", *measurement_columns]].copy()
    wide["source"] = data["source"] if "source" in data.columns else "csv_import"
    pieces = []
    for column in measurement_columns:
        indicator, unit = WIDE_COLUMNS[column]
        part = wide[["astronaut_id", "timestamp", "source", column]].rename(
            columns={column: "value"}
        )
        part["indicator"] = indicator
        part["unit"] = unit
        pieces.append(part)
    return pd.concat(pieces, ignore_index=True)[
        ["astronaut_id", "timestamp", "indicator", "value", "unit", "source"]
    ]

VALIDATION_RULES = {
    "heart_rate": ("bpm", 1.0, 250.0),
    "spo2": ("percent", 0.0, 100.0),
    "temperature": ("C", 25.0, 45.0),
    "sleep_duration": ("hours", 0.0, 24.0),
    "fatigue": ("score", 1.0, 5.0),
}


def validate_telemetry_chunk(frame: pd.DataFrame, label: str = "CSV") -> pd.DataFrame:
    """Vectorized strict validation suitable for large chunked imports."""
    data = frame.copy()
    required = ["astronaut_id", "timestamp", "indicator", "value", "unit", "source"]
    missing = [column for column in required if column not in data.columns]
    if missing:
        raise ValueError(f"{label}: missing required columns: {missing}")
    for column in ("astronaut_id", "indicator", "unit", "source"):
        data[column] = data[column].astype("string").str.strip()
    data["indicator"] = data["indicator"].str.lower()
    data["source"] = data["source"].str.lower()
    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True, errors="coerce")
    data["value"] = pd.to_numeric(data["value"], errors="coerce")
    missing_mask = data[required].isna().any(axis=1)
    if missing_mask.any():
        raise ValueError(f"{label}: {int(missing_mask.sum())} rows have missing IDs, timestamps, indicators, units, sources, or numeric values.")
    if data["astronaut_id"].str.len().eq(0).any():
        raise ValueError(f"{label}: astronaut_id cannot be empty.")
    unknown = sorted(set(data["indicator"]) - set(VALIDATION_RULES))
    if unknown:
        raise ValueError(f"{label}: unsupported indicators: {unknown}")
    for indicator, (unit, minimum, maximum) in VALIDATION_RULES.items():
        mask = data["indicator"].eq(indicator)
        if not mask.any():
            continue
        wrong_unit = mask & data["unit"].ne(unit)
        if wrong_unit.any():
            raise ValueError(f"{label}: {indicator} requires unit '{unit}'.")
        out_of_range = mask & ~data["value"].between(minimum, maximum)
        if out_of_range.any():
            bad = data.loc[out_of_range, "value"].iloc[0]
            raise ValueError(f"{label}: {indicator} value {bad} is outside {minimum}–{maximum}.")
    duplicates = data.duplicated(["astronaut_id", "timestamp", "indicator"])
    if duplicates.any():
        raise ValueError(f"{label}: {int(duplicates.sum())} duplicate astronaut/timestamp/indicator rows.")
    return data.reset_index(drop=True)
