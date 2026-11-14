"""Personal baseline calculations — implementation comes later."""

import pandas as pd


def calculate_baseline(df):

    baseline = (
        df.groupby(
            ["astronaut_id", "indicator"]
        )["value"]
        .agg(
            mean="mean",
            std="std",
            minimum="min",
            maximum="max",
            count="count"
        )
        .reset_index()
    )

    # Handle indicators with only one reading
    baseline["std"] = baseline["std"].fillna(0)

    return baseline


def get_astronaut_baseline(baseline, astronaut_id):

    return baseline[
        baseline["astronaut_id"] == astronaut_id
    ].reset_index(drop=True)
