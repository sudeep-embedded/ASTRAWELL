"""Timestamp-preserving playback controller for imported telemetry."""
from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Callable, Iterable


class ReplayController:
    """Threaded playback over an ordered sequence of source timestamps.

    The sequence contains timestamps only (small even for multi-million-row files).
    The callback is responsible for fetching/processing the records at each timestamp.
    """
    def __init__(self, timestamps: Iterable[str], on_timestamp: Callable[[str], None], speed: float = 1.0):
        self.timestamps = list(timestamps)
        self.on_timestamp = on_timestamp
        self.speed = max(float(speed), 0.01)
        self.index = 0
        self.status = "READY" if self.timestamps else "EMPTY"
        self.current_timestamp = None
        self.last_error = ""
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="astrawell-csv-replay")
        self._thread.start()

    @property
    def progress(self) -> float:
        with self._lock:
            return self.index / len(self.timestamps) if self.timestamps else 0.0

    def start(self):
        with self._lock:
            if not self.timestamps:
                self.status = "EMPTY"
            elif self.index >= len(self.timestamps):
                self.status = "COMPLETED"
            else:
                self.status = "RUNNING"
                self._wake.set()

    def pause(self):
        with self._lock:
            if self.status == "RUNNING":
                self.status = "PAUSED"
                self._wake.set()

    def resume(self):
        self.start()

    def stop(self):
        with self._lock:
            if self.status not in ("EMPTY", "COMPLETED"):
                self.status = "STOPPED"
                self._wake.set()

    def reset(self):
        with self._lock:
            self.index = 0
            self.current_timestamp = None
            self.last_error = ""
            self.status = "READY" if self.timestamps else "EMPTY"
            self._wake.set()

    def set_speed(self, speed: float):
        with self._lock:
            self.speed = max(float(speed), 0.01)
            self._wake.set()

    def _run(self):
        while True:
            self._wake.wait()
            self._wake.clear()
            while True:
                with self._lock:
                    if self.status != "RUNNING" or self.index >= len(self.timestamps):
                        if self.index >= len(self.timestamps) and self.timestamps:
                            self.status = "COMPLETED"
                        break
                    timestamp = self.timestamps[self.index]
                    previous = self.timestamps[self.index - 1] if self.index > 0 else None
                    speed = self.speed
                if previous is not None:
                    try:
                        delta = max((datetime.fromisoformat(timestamp.replace("Z", "+00:00")) -
                                     datetime.fromisoformat(previous.replace("Z", "+00:00"))).total_seconds(), 0)
                    except ValueError:
                        delta = 0
                    deadline = time.monotonic() + delta / max(speed, 0.01)
                    while time.monotonic() < deadline:
                        with self._lock:
                            if self.status != "RUNNING":
                                break
                        time.sleep(min(0.05, max(deadline - time.monotonic(), 0)))
                with self._lock:
                    if self.status != "RUNNING":
                        break
                try:
                    self.on_timestamp(timestamp)
                    with self._lock:
                        self.current_timestamp = timestamp
                        self.index += 1
                except Exception as exc:
                    with self._lock:
                        self.last_error = f"{type(exc).__name__}: {exc}"
                        self.status = "ERROR"
                    break
