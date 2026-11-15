"""Personal baseline calculations for long-format astronaut telemetry."""
import pandas as pd


def calculate_baseline(df):
    """Calculate per-astronaut/per-indicator descriptive baselines."""
    required = {"astronaut_id", "indicator", "value"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing baseline columns: {sorted(missing)}")
    data = df.copy()
    data["value"] = pd.to_numeric(data["value"], errors="coerce")
    data = data.dropna(subset=["astronaut_id", "indicator", "value"])
    if data.empty:
        return pd.DataFrame(columns=["astronaut_id", "indicator", "mean", "std", "minimum", "maximum", "count"])
    result = (
        data.groupby(["astronaut_id", "indicator"], dropna=False)["value"]
        .agg(mean="mean", std="std", minimum="min", maximum="max", count="count")
        .reset_index()
    )
    # A single reading has no estimable sample standard deviation.
    result["std"] = result["std"].fillna(0.0)
    return result


def get_astronaut_baseline(baseline, astronaut_id):
    return baseline[baseline["astronaut_id"] == astronaut_id].reset_index(drop=True)
