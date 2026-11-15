import pandas as pd
from analytics.extended import (
    period_summary, crew_comparison, correlation_matrix, linear_trend_estimates
)


def sample_data():
    rows = []
    for aid, offset in [("A1", 0), ("A2", 5)]:
        for i in range(12):
            rows.append({
                "astronaut_id": aid,
                "ts": pd.Timestamp("2026-01-01", tz="UTC") + pd.Timedelta(hours=i),
                "heart_rate": 60 + i + offset,
                "spo2": 98 - i * 0.1,
                "temperature": 36.5 + i * 0.01,
                "sleep_duration": 7.0,
                "fatigue": 2 + i * 0.05,
            })
    return pd.DataFrame(rows)


def test_period_summary_daily():
    result = period_summary(sample_data(), "D")
    assert not result.empty
    assert "heart_rate_mean" in result


def test_crew_comparison_uses_per_person_baseline():
    result = crew_comparison(sample_data())
    assert set(result["astronaut_id"]) == {"A1", "A2"}
    assert "largest_baseline_deviation" in result


def test_correlation_matrix_shape():
    result = correlation_matrix(sample_data())
    assert "heart_rate" in result.columns
    assert result.loc["heart_rate", "heart_rate"] == 1.0


def test_linear_trend_estimate():
    result = linear_trend_estimates(sample_data(), horizon_hours=3)
    assert not result.empty
    assert (result["points_used"] >= 6).all()
