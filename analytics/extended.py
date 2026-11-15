"""Descriptive analytics for ASTRAWELL's wide-format telemetry.

All outputs are research/demo aids. Correlation is not causation; linear
extrapolation is experimental and is not a clinical prediction.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

INDICATORS = ["heart_rate", "spo2", "temperature", "sleep_duration", "fatigue"]


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["astronaut_id", "ts", *INDICATORS])
    out = df.copy()
    if "timestamp" in out and "ts" not in out:
        out = out.rename(columns={"timestamp": "ts"})
    out["ts"] = pd.to_datetime(out["ts"], errors="coerce", utc=True)
    for col in INDICATORS:
        if col not in out:
            out[col] = np.nan
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out.dropna(subset=["ts"]).sort_values("ts")


def period_summary(df: pd.DataFrame, period: str = "D") -> pd.DataFrame:
    """Aggregate readings into daily (D), weekly (W), or monthly (MS) buckets."""
    if period not in {"D", "W", "MS"}:
        raise ValueError("period must be D, W, or MS")
    data = _prepare(df)
    if data.empty:
        return pd.DataFrame()
    grouped = data.set_index("ts").groupby("astronaut_id").resample(period)
    agg = grouped[INDICATORS].agg(["mean", "min", "max", "count"])
    agg.columns = [f"{col}_{stat}" for col, stat in agg.columns]
    return agg.reset_index().rename(columns={"ts": "period"})


def crew_comparison(df: pd.DataFrame) -> pd.DataFrame:
    """Compare latest value to each astronaut's own baseline (not a population norm)."""
    data = _prepare(df)
    if data.empty:
        return pd.DataFrame()
    rows = []
    for aid, group in data.groupby("astronaut_id"):
        group = group.sort_values("ts")
        latest = group.iloc[-1]
        row = {"astronaut_id": aid, "timestamp": latest["ts"]}
        scores = []
        for col in INDICATORS:
            values = group[col].dropna()
            current = latest[col]
            row[col] = current
            if len(values) >= 5 and pd.notna(current):
                mean = float(values.mean())
                std = float(values.std(ddof=1))
                floor = max(abs(mean) * 0.005, 0.05)
                z = (float(current) - mean) / max(std, floor)
                row[f"{col}_z"] = round(z, 2)
                scores.append(abs(z))
            else:
                row[f"{col}_z"] = np.nan
        row["largest_baseline_deviation"] = round(max(scores), 2) if scores else np.nan
        rows.append(row)
    return pd.DataFrame(rows).sort_values("largest_baseline_deviation", ascending=False, na_position="last")


def correlation_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Pearson correlation matrix across available indicators."""
    data = _prepare(df)
    if data.empty:
        return pd.DataFrame()
    return data[INDICATORS].corr(method="pearson", min_periods=5)


def linear_trend_estimates(df: pd.DataFrame, horizon_hours: int = 6, max_points: int = 48) -> pd.DataFrame:
    """Experimental least-squares extrapolation from recent points; not a validated forecast."""
    if horizon_hours < 1 or max_points < 6:
        raise ValueError("horizon_hours must be >=1 and max_points must be >=6")
    data = _prepare(df)
    if data.empty:
        return pd.DataFrame()
    rows = []
    for aid, group in data.groupby("astronaut_id"):
        group = group.sort_values("ts")
        for col in INDICATORS:
            s = group[["ts", col]].dropna().tail(max_points)
            if len(s) < 6:
                continue
            x = (s["ts"] - s["ts"].iloc[0]).dt.total_seconds().to_numpy() / 3600.0
            y = s[col].to_numpy(dtype=float)
            if np.unique(x).size < 3:
                continue
            slope, intercept = np.polyfit(x, y, 1)
            predicted = float(intercept + slope * (x[-1] + horizon_hours))
            rows.append({
                "astronaut_id": aid, "indicator": col,
                "latest_value": float(y[-1]), "slope_per_hour": float(slope),
                "estimate_after_hours": horizon_hours, "experimental_estimate": predicted,
                "points_used": len(s),
            })
    return pd.DataFrame(rows)
