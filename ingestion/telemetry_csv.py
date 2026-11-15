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
