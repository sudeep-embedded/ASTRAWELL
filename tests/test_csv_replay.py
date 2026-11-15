import time

import pandas as pd
import pytest

from ingestion.replay import ReplayController
from ingestion.telemetry_csv import prepare_telemetry_csv, validate_telemetry_chunk


def test_chunk_validator_rejects_bad_ranges_and_duplicate_keys():
    frame = prepare_telemetry_csv(pd.DataFrame({
        "astronaut_id": ["AST001"], "timestamp": ["2026-11-14T00:00:00Z"],
        "heart_rate_bpm": [999],
    }))
    with pytest.raises(ValueError, match="outside"):
        validate_telemetry_chunk(frame)

    duplicate = pd.DataFrame([
        {"astronaut_id": "AST001", "timestamp": "2026-11-14T00:00:00Z",
         "indicator": "heart_rate", "value": 70, "unit": "bpm", "source": "csv_new"},
        {"astronaut_id": "AST001", "timestamp": "2026-11-14T00:00:00Z",
         "indicator": "heart_rate", "value": 71, "unit": "bpm", "source": "csv_new"},
    ])
    with pytest.raises(ValueError, match="duplicate"):
        validate_telemetry_chunk(duplicate)


def test_replay_preserves_timestamp_order_and_completes():
    seen = []
    timestamps = [
        "2026-11-14T00:00:00+00:00",
        "2026-11-14T00:00:00+00:00",
        "2026-11-14T00:00:00+00:00",
    ]
    replay = ReplayController(timestamps, seen.append, speed=60)
    replay.start()
    deadline = time.time() + 2
    while replay.status not in ("COMPLETED", "ERROR") and time.time() < deadline:
        time.sleep(0.01)
    assert replay.status == "COMPLETED"
    assert seen == timestamps
    assert replay.progress == 1.0


def test_replay_reset_and_stop_controls():
    seen = []
    replay = ReplayController(["2026-11-14T00:00:00+00:00"], seen.append, speed=60)
    replay.start()
    deadline = time.time() + 2
    while replay.status not in ("COMPLETED", "ERROR") and time.time() < deadline:
        time.sleep(0.01)
    replay.reset()
    assert replay.status == "READY"
    assert replay.index == 0
    assert replay.current_timestamp is None
    replay.start()
    deadline = time.time() + 2
    while replay.status not in ("COMPLETED", "ERROR") and time.time() < deadline:
        time.sleep(0.01)
    assert len(seen) == 2
    assert replay.status == "COMPLETED"
