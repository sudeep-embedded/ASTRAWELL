import pandas as pd
import pytest

from ingestion.telemetry_csv import prepare_telemetry_csv


def test_wide_csv_is_normalized_to_long_format_for_all_indicators():
    frame = pd.DataFrame({
        "astronaut_id": ["AST001", "AST002"],
        "timestamp": ["2026-11-14T00:00:00Z", "2026-11-14T00:00:01Z"],
        "heart_rate_bpm": [70, 72],
        "spo2_percent": [98.0, 97.5],
        "temperature_C": [36.5, 36.6],
        "sleep_duration_hours": [7.5, 7.4],
        "fatigue_score": [2, 2],
    })
    result = prepare_telemetry_csv(frame)
    assert len(result) == 10
    assert set(result["indicator"]) == {
        "heart_rate", "spo2", "temperature", "sleep_duration", "fatigue"
    }
    assert set(result["unit"]) == {"bpm", "percent", "C", "hours", "score"}
    assert set(result["astronaut_id"]) == {"AST001", "AST002"}


def test_long_csv_is_preserved_and_source_is_defaulted():
    frame = pd.DataFrame([{
        "astronaut_id": "AST001", "timestamp": "2026-11-14T00:00:00Z",
        "indicator": "heart_rate", "value": 70, "unit": "bpm"
    }])
    result = prepare_telemetry_csv(frame)
    assert list(result.columns) == [
        "astronaut_id", "timestamp", "indicator", "value", "unit", "source"
    ]
    assert result.loc[0, "source"] == "csv_import"


def test_unsupported_csv_schema_fails_with_actionable_error():
    with pytest.raises(ValueError, match="Unsupported CSV schema"):
        prepare_telemetry_csv(pd.DataFrame({"id": ["AST001"], "hr": [70]}))


def test_wide_csv_with_partial_indicators_is_supported():
    frame = pd.DataFrame({
        "astronaut_id": ["AST001"], "timestamp": ["2026-11-14T00:00:00Z"],
        "heart_rate_bpm": [70], "spo2_percent": [98.0],
    })
    result = prepare_telemetry_csv(frame)
    assert set(result["indicator"]) == {"heart_rate", "spo2"}
    assert len(result) == 2
