"""Extended descriptive analytics and export helpers for ASTRAWELL.

All outputs are decision-support summaries over supplied telemetry. Forecasts are
experimental linear extrapolations, not validated predictions or medical advice.
"""
from __future__ import annotations

from io import BytesIO
from typing import Iterable

import numpy as np
import pandas as pd

INDICATORS = ["heart_rate", "spo2", "temperature", "sleep_duration", "fatigue"]
LABELS = {
    "heart_rate": ("Heart rate", "bpm"),
    "spo2": ("SpO₂", "%"),
    "temperature": ("Temperature", "°C"),
    "sleep_duration": ("Sleep duration", "h"),
    "fatigue": ("Fatigue", "/5"),
}


def _clean(frame: pd.DataFrame) -> pd.DataFrame:
    d = frame.copy()
    if "ts" not in d and "timestamp" in d:
        d = d.rename(columns={"timestamp": "ts"})
    if "ts" not in d:
        raise ValueError("Telemetry must contain a ts or timestamp column.")
    d["ts"] = pd.to_datetime(d["ts"], errors="coerce", utc=True)
    d = d.dropna(subset=["ts"])
    for col in INDICATORS:
        if col in d:
            d[col] = pd.to_numeric(d[col], errors="coerce")
    return d.sort_values("ts")


def period_summary(frame: pd.DataFrame, period: str = "D") -> pd.DataFrame:
    """Return per-astronaut indicator means and sample counts by period."""
    d = _clean(frame)
    freq = {"daily": "D", "weekly": "W-MON", "monthly": "MS",
            "D": "D", "W": "W-MON", "M": "MS", "MS": "MS"}.get(period)
    if freq is None:
        raise ValueError("period must be daily, weekly, or monthly")
    available = [c for c in INDICATORS if c in d]
    if not available:
        return pd.DataFrame()
    if "astronaut_id" not in d:
        d["astronaut_id"] = "UNKNOWN"
    d["period"] = d["ts"].dt.to_period(freq).dt.start_time
    grouped = d.groupby(["astronaut_id", "period"], dropna=False)[available]
    means = grouped.mean().reset_index()
    counts = grouped.size().rename("reading_count").reset_index()
    return means.merge(counts, on=["astronaut_id", "period"]).sort_values(
        ["astronaut_id", "period"]
    )


def crew_comparison(frame: pd.DataFrame) -> pd.DataFrame:
    """Compare each crew member's latest values against their own historical mean/std."""
    d = _clean(frame)
    if "astronaut_id" not in d:
        return pd.DataFrame()
    rows = []
    for aid, group in d.groupby("astronaut_id"):
        row = {"Astronaut": aid, "Readings": len(group)}
        for col in INDICATORS:
            if col not in group:
                continue
            values = group[col].dropna()
            if values.empty:
                continue
            latest = float(values.iloc[-1])
            mean = float(values.mean())
            std = float(values.std(ddof=1)) if len(values) > 1 else 0.0
            row[f"{col}_current"] = latest
            row[f"{col}_baseline"] = mean
            row[f"{col}_z"] = (latest - mean) / std if std > 1e-12 else 0.0
        rows.append(row)
    return pd.DataFrame(rows)


def indicator_correlations(frame: pd.DataFrame, min_observations: int = 12) -> pd.DataFrame:
    """Pearson correlations across available indicators; omit pairs with too few rows."""
    d = _clean(frame)
    cols = [c for c in INDICATORS if c in d and d[c].notna().sum() >= min_observations]
    if len(cols) < 2:
        return pd.DataFrame()
    return d[cols].corr(method="pearson", min_periods=min_observations)


def trend_projection(frame: pd.DataFrame, steps: int = 6, lookback: int = 24) -> pd.DataFrame:
    """Experimental least-squares linear extrapolation over the last lookback samples."""
    if steps < 1 or lookback < 3:
        raise ValueError("steps must be positive and lookback must be at least 3")
    d = _clean(frame)
    rows = []
    for col in INDICATORS:
        if col not in d:
            continue
        series = d[["ts", col]].dropna().tail(lookback)
        if len(series) < 6:
            continue
        y = series[col].to_numpy(dtype=float)
        x = np.arange(len(y), dtype=float)
        slope, intercept = np.polyfit(x, y, 1)
        fitted = intercept + slope * x
        residual = y - fitted
        rmse = float(np.sqrt(np.mean(residual ** 2)))
        for step in range(1, steps + 1):
            rows.append({
                "indicator": col,
                "step_ahead": step,
                "projected_value": float(intercept + slope * (len(y) - 1 + step)),
                "slope_per_reading": float(slope),
                "fit_rmse": rmse,
                "samples_used": len(y),
                "last_observed_at": series["ts"].iloc[-1],
            })
    return pd.DataFrame(rows)


def build_report(frame: pd.DataFrame, astronaut_id: str | None = None) -> dict:
    d = _clean(frame)
    if astronaut_id and "astronaut_id" in d:
        d = d[d["astronaut_id"].astype(str) == str(astronaut_id)]
    if d.empty:
        return {"summary": pd.DataFrame(), "comparison": pd.DataFrame(),
                "correlations": pd.DataFrame(), "projection": pd.DataFrame(),
                "readings": d}
    return {
        "summary": period_summary(d, "daily"),
        "comparison": crew_comparison(d),
        "correlations": indicator_correlations(d),
        "projection": trend_projection(d),
        "readings": d,
    }


def report_pdf(report: dict, title: str = "ASTRAWELL Health Intelligence Report") -> bytes:
    """Create a compact PDF report. Requires reportlab (listed in requirements)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    )

    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4),
                            rightMargin=12*mm, leftMargin=12*mm,
                            topMargin=12*mm, bottomMargin=12*mm)
    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Title"]),
             Paragraph("Research prototype • Synthetic/imported telemetry • Not a diagnosis",
                       styles["Normal"]), Spacer(1, 6*mm)]

    def add_table(heading: str, df: pd.DataFrame, max_rows: int = 30):
        story.append(Paragraph(heading, styles["Heading2"]))
        if df is None or df.empty:
            story.append(Paragraph("Insufficient data for this section.", styles["Normal"]))
            story.append(Spacer(1, 3*mm))
            return
        view = df.head(max_rows).copy()
        view = view.replace({np.nan: "—", np.inf: "—", -np.inf: "—"})
        data = [[str(c) for c in view.columns]]
        for row in view.itertuples(index=False, name=None):
            data.append([str(v)[:48] for v in row])
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16324F")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#F1F5F9")]),
        ]))
        story.append(table)
        story.append(Spacer(1, 4*mm))

    readings = report.get("readings", pd.DataFrame())
    if not readings.empty:
        story.append(Paragraph(
            f"Records: {len(readings)} • Crew: {readings['astronaut_id'].nunique() if 'astronaut_id' in readings else 1} "
            f"• Window: {readings['ts'].min()} to {readings['ts'].max()}",
            styles["Normal"]))
    add_table("Daily summaries", report.get("summary"))
    add_table("Crew comparison (current values and personal z-scores)",
              report.get("comparison"))
    add_table("Indicator correlations", report.get("correlations").reset_index()
              if report.get("correlations") is not None and not report.get("correlations").empty
              else pd.DataFrame())
    add_table("Experimental trend projections", report.get("projection"))
    story.append(Paragraph(
        "Interpretation: descriptive analytics and linear extrapolations are experimental. "
        "Thresholds and outputs are not clinically validated and must not replace onboard "
        "medical procedures or professional judgement.", styles["Italic"]))
    doc.build(story)
    return output.getvalue()
