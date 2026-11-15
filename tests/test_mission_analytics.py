import pandas as pd

from analytics.mission_analytics import (
    period_summary, crew_comparison, indicator_correlations, trend_projection, build_report
)


def sample_frame():
    ts = pd.date_range("2026-01-01", periods=30, freq="h", tz="UTC")
    return pd.DataFrame({
        "astronaut_id": ["A"] * 30 + ["B"] * 30,
        "ts": list(ts) * 2,
        "heart_rate": list(range(60, 90)) + list(range(70, 100)),
        "spo2": [98 - i * .02 for i in range(30)] * 2,
        "temperature": [36.5 + i * .01 for i in range(30)] * 2,
        "sleep_duration": [7.5] * 60,
        "fatigue": [2 + i * .01 for i in range(30)] * 2,
    })


def test_period_summary_has_crew_and_period():
    result = period_summary(sample_frame(), "daily")
    assert {"astronaut_id", "period", "reading_count"}.issubset(result.columns)
    assert len(result) > 0


def test_crew_comparison_has_one_row_per_astronaut():
    result = crew_comparison(sample_frame())
    assert set(result["Astronaut"]) == {"A", "B"}


def test_correlations_are_bounded():
    result = indicator_correlations(sample_frame())
    assert not result.empty
    assert result.max().max() <= 1.0
    assert result.min().min() >= -1.0


def test_trend_projection_is_experimental_and_numeric():
    result = trend_projection(sample_frame(), steps=3)
    assert len(result) == 15
    assert result["projected_value"].notna().all()


def test_build_report_can_scope_one_astronaut():
    result = build_report(sample_frame(), "A")
    assert set(result["readings"]["astronaut_id"]) == {"A"}
