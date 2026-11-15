"""
ASTRAWELL - Autonomous Astronaut Health Intelligence System
Mission Control Dashboard  (run:  streamlit run app.py   |  needs streamlit >= 1.37)

Existing backend modules are reused exactly as the previous app.py called them.
Live/historical telemetry for the dashboard lives in its own SQLite file
(data/astrawell_live.db), so NO migration of database/db.py's schema is needed.
Simulated rows are always tagged source='simulated'; CSV rows 'csv_import'.
"""
from __future__ import annotations

import hashlib
import html
import io
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analytics.baseline import calculate_baseline
from analytics.anomaly_detector import detect_anomalies
from analytics.rule_engine import evaluate_health_patterns
from analytics.mission_analytics import (period_summary, crew_comparison, deterioration_comparison, indicator_correlations, trend_projection, build_report, report_pdf)
from preprocessing.validator import validate_health_data
from ingestion.telemetry_csv import prepare_telemetry_csv, validate_telemetry_chunk
from ingestion.replay import ReplayController
from preprocessing.normalizer import normalize_health_data
from decision_support.alert_generator import generate_alerts
from decision_support.explanations import explain_alert
from database.db import (
    initialize_database, save_health_readings, save_baselines,
    save_alerts, get_alert_history,
)

# ============================== CONFIG ==============================
DB_PATH = Path("data/astrawell_live.db")
FMT = "%Y-%m-%d %H:%M:%S"
CYAN, BLUE, GREEN, AMBER, RED, MUTED, TEXT = (
    "#3dd9f0", "#4f8cff", "#2ee59d", "#ffb020", "#ff4d5e", "#6f8aa3", "#e5edf7")
# column: (label, unit, decimals, minimum std-dev floor)
INDICATORS = {
    "heart_rate": ("HEART RATE", "BPM", 0, 2.0),
    "spo2": ("SpO₂", "%", 1, 0.4),
    "temperature": ("BODY TEMP", "°C", 2, 0.12),
    "sleep_duration": ("SLEEP", "h", 1, 0.5),
    "fatigue": ("FATIGUE", "/5", 0, 0.5),
}
Z_FLAG, Z_WARN = 2.5, 1.5
RANGES = {"1 minute": timedelta(minutes=1), "5 minutes": timedelta(minutes=5),
          "15 minutes": timedelta(minutes=15), "1 hour": timedelta(hours=1),
          "6 hours": timedelta(hours=6), "24 hours": timedelta(hours=24),
          "7 days": timedelta(days=7), "30 days": timedelta(days=30)}
LIVE_RANGES = {"1 minute": timedelta(minutes=1), "5 minutes": timedelta(minutes=5),
               "15 minutes": timedelta(minutes=15), "1 hour": timedelta(hours=1)}
SOURCES = {"All sources": "all", "Simulated": "simulated", "CSV import": "csv_import"}
# Thirty deterministic synthetic crew profiles. Values are illustrative baselines,
# not measurements or medically validated limits.
CREW = [f"AST{i:03d}" for i in range(1, 31)]
PROFILE = {
    aid: (
        60 + ((i * 7) % 19),                 # resting HR baseline: 60–78 bpm
        round(96.5 + ((i * 13) % 25) / 10, 1),  # SpO2 baseline: 96.5–98.9%
        round(36.4 + ((i * 11) % 7) / 10, 2),   # temperature: 36.4–37.0 C
        round(6.2 + ((i * 17) % 19) / 10, 1),   # sleep: 6.2–8.0 h
    )
    for i, aid in enumerate(CREW, start=1)
}
KIND_COLOR = {"TELEMETRY": CYAN, "ANOMALY": AMBER, "ALERT": RED,
              "IMPORT": BLUE, "ANALYSIS": GREEN}

# ============================== DATABASE ==============================
SCHEMA = """
CREATE TABLE IF NOT EXISTS telemetry(
  astronaut_id TEXT NOT NULL, ts TEXT NOT NULL, source TEXT NOT NULL,
  heart_rate REAL, spo2 REAL, temperature REAL, sleep_duration REAL, fatigue REAL,
  PRIMARY KEY (astronaut_id, ts, source)) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS ix_tel_ts ON telemetry(ts);
CREATE TABLE IF NOT EXISTS live_alerts(
  alert_id TEXT PRIMARY KEY, astronaut_id TEXT, severity TEXT, indicators TEXT,
  detected_at TEXT, summary TEXT, action TEXT, source TEXT,
  status TEXT DEFAULT 'UNACKNOWLEDGED', acked_at TEXT);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, kind TEXT, astronaut_id TEXT, message TEXT);
CREATE TABLE IF NOT EXISTS imports(file_hash TEXT PRIMARY KEY, name TEXT, ts TEXT);
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)  # autocommit; we BEGIN manually
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.execute("PRAGMA busy_timeout=30000")
    return c


@contextmanager
def transaction():
    """Short write transaction; BEGIN IMMEDIATE serialises writers across threads/sessions."""
    c = _connect()
    try:
        c.execute("BEGIN IMMEDIATE")
        yield c
        c.execute("COMMIT")
    except Exception:
        try:
            c.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        c.close()


def read_df(sql: str, params=()) -> pd.DataFrame:
    c = _connect()
    try:
        return pd.read_sql_query(sql, c, params=params)
    finally:
        c.close()


def init_live_db():
    c = _connect()
    try:
        c.executescript(SCHEMA)
    finally:
        c.close()


def now_ts() -> str:
    return datetime.now(timezone.utc).strftime(FMT)


def _event(c, kind, aid, msg):
    c.execute("INSERT INTO events(ts,kind,astronaut_id,message) VALUES (?,?,?,?)",
              (now_ts(), kind, aid, msg))
    c.execute("DELETE FROM events WHERE id < (SELECT MAX(id) FROM events) - 2000")


def log_event(kind, aid, msg):
    with transaction() as c:
        _event(c, kind, aid, msg)


def insert_telemetry(rows: list[tuple]) -> int:
    """Idempotent: PRIMARY KEY (astronaut_id, ts, source) + INSERT OR IGNORE => no duplicates."""
    if not rows:
        return 0
    with transaction() as c:
        before = c.total_changes
        c.executemany("INSERT OR IGNORE INTO telemetry VALUES (?,?,?,?,?,?,?,?)", rows)
        return c.total_changes - before


def store_alert(aid, severity, indicators, detected_at, summary, action, source) -> int:
    """Deterministic ID = hash(astronaut, indicator set, 30-min bucket, source) -> unique + de-duplicated."""
    bucket = int(pd.Timestamp(detected_at).timestamp() // 1800)
    key = f"{aid}|{','.join(sorted(indicators))}|{bucket}|{source}"
    alert_id = "ALR-" + hashlib.sha1(key.encode()).hexdigest()[:8].upper()
    with transaction() as c:
        before = c.total_changes
        c.execute("INSERT OR IGNORE INTO live_alerts(alert_id,astronaut_id,severity,indicators,"
                  "detected_at,summary,action,source) VALUES (?,?,?,?,?,?,?,?)",
                  (alert_id, aid, str(severity), ", ".join(indicators), detected_at,
                   summary, action, source))
        created = c.total_changes > before
        if created:
            _event(c, "ANOMALY", aid, f"Anomaly detected: {', '.join(indicators)}")
            _event(c, "ALERT", aid, f"{alert_id} generated ({severity})")
    return int(created)


def ack_alert(alert_id: str):
    with transaction() as c:
        before = c.total_changes
        c.execute("UPDATE live_alerts SET status='ACKNOWLEDGED', acked_at=? "
                  "WHERE alert_id=? AND status='UNACKNOWLEDGED'", (now_ts(), alert_id))
        if c.total_changes > before:
            _event(c, "ALERT", "—", f"{alert_id} acknowledged")


def register_import(file_hash: str, name: str) -> bool:
    with transaction() as c:
        before = c.total_changes
        c.execute("INSERT OR IGNORE INTO imports VALUES (?,?,?)", (file_hash, name, now_ts()))
        return c.total_changes > before


def _get(obj, key, default=None):
    return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)


def ingest_alerts(alerts, source, default_aid, default_ts) -> int:
    """Convert pipeline alerts (via explain_alert) into stored, de-duplicated alert rows."""
    created = 0
    for al in alerts or []:
        ex = explain_alert(al)
        inds = [str(d.get("indicator", "?")) for d in ex.get("details", [])] or ["unspecified"]
        aid = str(_get(al, "astronaut_id", default_aid))
        try:
            ts = pd.Timestamp(_get(al, "timestamp", default_ts)).strftime(FMT)
        except Exception:
            ts = pd.Timestamp(default_ts).strftime(FMT)
        created += store_alert(aid, ex.get("priority", "medium"), inds, ts,
                               ex.get("summary", ""), ex.get("recommended_action", ""), source)
    return created


def to_long(df: pd.DataFrame) -> pd.DataFrame:
    """Wide telemetry -> the long format (astronaut_id, timestamp, indicator, value) the backend uses."""
    d = df.copy()
    d["timestamp"] = pd.to_datetime(d["ts"])
    return (d.melt(id_vars=["astronaut_id", "timestamp"], value_vars=list(INDICATORS),
                   var_name="indicator", value_name="value").dropna(subset=["value"]))


def import_long_frame(df: pd.DataFrame, label="CSV", source="csv_import"):
    """Mirror a normalised long-format DataFrame into the telemetry table (source='csv_import')."""
    wide = df.pivot_table(index=["astronaut_id", "timestamp"], columns="indicator",
                          values="value", aggfunc="mean").reset_index()
    for c in INDICATORS:
        if c not in wide:
            wide[c] = np.nan
    wide["ts"] = pd.to_datetime(wide["timestamp"], utc=True, errors="coerce").dt.strftime(FMT)
    wide = wide.dropna(subset=["ts"])
    rows = [(str(r["astronaut_id"]), r["ts"], source,
             *[None if pd.isna(r[c]) else float(r[c]) for c in INDICATORS])
            for r in wide.to_dict("records")]
    inserted = insert_telemetry(rows)
    log_event("IMPORT", "—", f"{label}: {len(rows)} rows parsed, {inserted} new")
    return len(rows), inserted

# ============================== TELEMETRY SOURCES / INGESTION ==============================


class TelemetrySource:
    """Integration point: subclass and implement read() to plug in real sensors / an API later."""
    name = "base"

    def read(self, now: datetime) -> list[tuple]:
        """Return [(astronaut_id, hr, spo2, temp, sleep_h, fatigue), ...]."""
        raise NotImplementedError

    def seed(self) -> list[tuple]:
        return []


class SimulatedSource(TelemetrySource):
    """SIMULATED telemetry (not real sensor data)."""
    name = "simulated"

    def __init__(self):
        self.rng = np.random.default_rng()
        self.s = {a: {"dev": 0.0, "ep": 0, "len": 1, "sleep": PROFILE[a][3]} for a in CREW}

    def sample(self, aid, when, p_episode):
        s, (hr0, sp0, t0, sl0), r = self.s[aid], PROFILE[aid], self.rng
        if s["ep"] == 0 and r.random() < p_episode:      # inject a multi-indicator anomaly episode
            s["ep"] = s["len"] = int(r.integers(10, 25))
        k = 0.0
        if s["ep"] > 0:
            k = float(np.sin(np.pi * (s["len"] - s["ep"]) / s["len"]))
            s["ep"] -= 1
        circ = np.sin(2 * np.pi * (when.hour + when.minute / 60 - 15) / 24)
        s["dev"] = 0.85 * s["dev"] + r.normal(0, 1.0)
        s["sleep"] = float(np.clip(0.98 * s["sleep"] + 0.02 * sl0 + r.normal(0, 0.08) - 0.15 * k, 3, 10))
        fat = int(np.clip(round(2 + (7.2 - s["sleep"]) * 0.7 + 1.8 * k + r.normal(0, 0.4)), 1, 5))
        return (round(hr0 + 3 * circ + 1.2 * s["dev"] + 22 * k, 1),
                round(min(sp0 + r.normal(0, 0.25) - 4.5 * k, 100), 1),
                round(t0 + 0.15 * circ + r.normal(0, 0.05) + 1.1 * k, 2),
                round(s["sleep"], 2), fat)

    def read(self, now):
        return [(a, *self.sample(a, now, 0.01)) for a in CREW]

    def seed(self):
        end = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        rows = [(a, (end - timedelta(hours=i)).strftime(FMT), self.name,
                 *self.sample(a, end - timedelta(hours=i), 0.004))
                for a in CREW for i in range(30 * 24, 0, -1)]
        for a in CREW:
            self.s[a].update(ep=0, dev=0.0)
        return rows


class Ingestor:
    """Single process-wide writer thread shared by every browser session."""

    def __init__(self, source: TelemetrySource):
        self.source, self.interval, self.running = source, 1.0, False
        self.monitor_mode, self.target_astronaut = "Crew (all astronauts)", None
        self.ticks, self.baselines, self.last_error = 0, {}, ""
        if source.name == "simulated":
            existing = set(read_df(
                "SELECT DISTINCT astronaut_id FROM telemetry WHERE source=?", (source.name,)
            )["astronaut_id"].tolist())
            missing = set(CREW) - existing
            if missing:
                rows = [row for row in source.seed() if row[0] in missing]
                if rows:
                    insert_telemetry(rows)
                    log_event("IMPORT", "SYSTEM",
                              f"Seeded {len(rows)} history rows for {len(missing)} new simulated crew profiles")
        else:
            n = read_df("SELECT COUNT(*) n FROM telemetry WHERE source=?", (source.name,))["n"][0]
            if n == 0:
                rows = source.seed()
                if rows:
                    insert_telemetry(rows)
                    log_event("IMPORT", "SYSTEM", f"Seeded {len(rows)} {source.name} history rows (30 days)")
        self.thread = threading.Thread(target=self._loop, daemon=True, name="astrawell-ingest")
        self.thread.start()

    def start(self):
        if not self.running:
            # A new live run is a clean session: preserve CSV imports, clear only
            # simulated-session telemetry/alerts and cached baselines.
            if self.source.name == "simulated":
                with transaction() as conn:
                    conn.execute("DELETE FROM telemetry WHERE source='simulated'")
                    conn.execute("DELETE FROM live_alerts WHERE source='simulated'")
                    _event(conn, "IMPORT", "SYSTEM", "Previous simulated session cleared; fresh session initialized")
                self.baselines.clear()
                self.ticks = 0
                for aid in CREW:
                    self.source.s[aid].update(dev=0.0, ep=0, len=1, sleep=PROFILE[aid][3])
                # list_astronauts is uncached; no selector cache needs invalidation.
                total_readings.clear()
                baseline_stats.clear()
            self.running = True
            log_event("TELEMETRY", "SYSTEM", f"Fresh monitoring session started ({self.source.name})")

    def stop(self):
        if self.running:
            self.running = False
            log_event("TELEMETRY", "SYSTEM", "Monitoring stopped")

    def _loop(self):
        while True:
            if self.running:
                try:
                    self._tick()
                except Exception as e:  # never kill the thread
                    self._report(f"Ingest error: {e}")
                time.sleep(max(0.5, self.interval))
            else:
                time.sleep(0.5)

    def _report(self, msg):
        if msg != self.last_error:
            self.last_error = msg
            try:
                log_event("ANALYSIS", "SYSTEM", msg[:300])
            except Exception:
                pass

    def _tick(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        samples = self.source.read(now)
        if self.monitor_mode == "Individual astronaut" and self.target_astronaut:
            samples = [sample for sample in samples if sample[0] == self.target_astronaut]
        rows = [(a, now.strftime(FMT), self.source.name, *v) for a, *v in samples]
        if not rows:
            return
        insert_telemetry(rows)
        self.ticks += 1
        if self.ticks % 20 == 1:
            log_event("TELEMETRY", "ALL", f"{len(rows)} readings ingested ({self.source.name})")
        if self.ticks % 5 == 0:
            for a in {r[0] for r in rows}:
                self._analyse(a)

    def _analyse(self, aid):
        """Run the existing backend pipeline on a recent window against a cached baseline."""
        try:
            if aid not in self.baselines or self.ticks % 100 == 0:
                hist = read_df("SELECT * FROM telemetry WHERE astronaut_id=? AND source=? "
                               "ORDER BY ts DESC LIMIT 2000", (aid, self.source.name))
                self.baselines[aid] = calculate_baseline(to_long(hist))
            win = read_df("SELECT * FROM telemetry WHERE astronaut_id=? AND source=? "
                          "ORDER BY ts DESC LIMIT 30", (aid, self.source.name)).iloc[::-1]
            anomalies = detect_anomalies(to_long(win), self.baselines[aid])
            alerts = generate_alerts(evaluate_health_patterns(anomalies), anomalies)
            ingest_alerts(alerts, self.source.name, aid, win["ts"].iloc[-1])
            self.last_error = ""
        except Exception as e:
            self._report(f"Pipeline error ({aid}): {type(e).__name__}: {e}")


@st.cache_resource
def get_ingestor() -> Ingestor:
    init_live_db()
    return Ingestor(SimulatedSource())

# ============================== QUERIES / ANALYTICS ==============================


def src_clause(source):
    if source == "all":
        return "", ()
    if source == "csv_import":
        return " AND source IN ('csv_import','csv_historical','csv_new')", ()
    if source == "csv_history":
        return " AND source IN ('csv_import','csv_historical')", ()
    return " AND source=?", (source,)


def list_astronauts(source: str = "all") -> list[str]:
    """Read current IDs from SQLite so imports cannot leave stale selector options."""
    clause, params = src_clause(source)
    return read_df(
        f"SELECT DISTINCT astronaut_id FROM telemetry WHERE 1=1{clause} ORDER BY astronaut_id",
        params,
    )["astronaut_id"].dropna().astype(str).tolist()


@st.cache_data(ttl=10, show_spinner=False)
def total_readings() -> int:
    return int(read_df("SELECT COUNT(*) n FROM telemetry")["n"][0])


@st.cache_data(ttl=30, show_spinner=False)
def baseline_stats(aid, source) -> dict:
    """Personal baseline (mean, std) per indicator, aggregated in SQL (no full-history load)."""
    cols = ",".join(f"AVG({c}) m_{c}, AVG({c}*{c}) q_{c}, COUNT({c}) n_{c}" for c in INDICATORS)
    baseline_source = source
    if source == "csv_import":
        historical_n = read_df(
            "SELECT COUNT(*) n FROM telemetry WHERE astronaut_id=? AND source IN ('csv_historical','csv_import')",
            (aid,),
        )["n"].iloc[0]
        baseline_source = "csv_history" if historical_n else "csv_new"
    clause, p = src_clause(baseline_source)
    row = read_df(f"SELECT {cols} FROM telemetry WHERE astronaut_id=?{clause}", (aid, *p)).iloc[0]
    out = {}
    for c, (_, _, _, floor) in INDICATORS.items():
        n = row[f"n_{c}"]
        if pd.notna(n) and n >= 5:
            m = float(row[f"m_{c}"])
            var = max(float(row[f"q_{c}"]) - m * m, 0.0) * n / (n - 1)
            out[c] = (m, max(var ** 0.5, floor))
    return out


def latest_snapshot(aid, source):
    clause, p = src_clause(source)
    df = read_df(f"SELECT * FROM telemetry WHERE astronaut_id=?{clause} ORDER BY ts DESC LIMIT 200",
                 (aid, *p))
    if df.empty:
        return {}, None
    return df.bfill().iloc[0][list(INDICATORS)].to_dict(), df["ts"].iloc[0]


def load_window(aid, source, delta) -> pd.DataFrame:
    """Window is anchored to the astronaut's latest reading, so historical CSVs display too."""
    clause, p = src_clause(source)
    end = read_df(f"SELECT MAX(ts) m FROM telemetry WHERE astronaut_id=?{clause}", (aid, *p))["m"][0]
    if end is None or pd.isna(end):
        return pd.DataFrame()
    start = (pd.Timestamp(end) - delta).strftime(FMT)
    df = read_df(f"SELECT * FROM telemetry WHERE astronaut_id=? AND ts>=? AND ts<=?{clause} ORDER BY ts",
                 (aid, start, end, *p))
    df["ts"] = pd.to_datetime(df["ts"])
    if len(df) > 1500:  # downsample for plotting only
        step = max(int((df["ts"].iloc[-1] - df["ts"].iloc[0]).total_seconds() / 1500), 1)
        df = df.set_index("ts")[list(INDICATORS)].resample(f"{step}s").mean().dropna(how="all").reset_index()
    return df


def status_of(z: float):
    a = abs(z)
    return ("DEVIATING", RED) if a >= Z_FLAG else ("WATCH", AMBER) if a >= Z_WARN else ("NOMINAL", GREEN)


def sev_color(s) -> str:
    s = str(s).lower()
    return RED if s in ("critical", "high", "urgent") else AMBER if s in ("medium", "moderate", "warning") else CYAN


def crew_snapshot(source):
    out = []
    for a in list_astronauts(source):
        vals, last = latest_snapshot(a, source)
        stats = baseline_stats(a, source)
        z = {c: (vals[c] - stats[c][0]) / stats[c][1]
             for c in INDICATORS if c in stats and pd.notna(vals.get(c))}
        out.append({"id": a, "vals": vals, "last": last, "z": z,
                    "worst": max((abs(v) for v in z.values()), default=0.0)})
    return out


def intelligence(vals, stats, d):
    rows, flagged = [], {}
    for col, (label, unit, dec, _) in INDICATORS.items():
        v = vals.get(col)
        if col not in stats or pd.isna(v):
            continue
        m, sd = stats[col]
        z = (v - m) / sd
        s = d[col].dropna() if col in d else pd.Series(dtype=float)
        trend = "n/a"
        if len(s) >= 6:
            k = len(s) // 3
            tr = (s.iloc[-k:].mean() - s.iloc[:k].mean()) / sd
            trend = "↑ rising" if tr > 0.5 else "↓ falling" if tr < -0.5 else "→ stable"
        if abs(z) >= Z_WARN:
            flagged[col] = z
        rows.append({"Indicator": label, "Current": f"{v:.{dec}f} {unit}",
                     "Baseline": f"{m:.{dec + 1}f} ± {sd:.{dec + 1}f}", "z-score": round(z, 2),
                     "Status": status_of(z)[0], "Trend": trend,
                     "Explanation": (f"{abs(z):.1f}σ {'above' if z > 0 else 'below'} personal baseline"
                                     if abs(z) >= Z_WARN else "Within personal baseline")})
    pats = []
    if len(flagged) >= 2:
        pats.append("Multi-indicator deviation: " + ", ".join(
            f"{INDICATORS[c][0]} {'↑' if z > 0 else '↓'}" for c, z in flagged.items()))
    f = flagged
    if f.get("heart_rate", 0) > 0 and f.get("spo2", 0) < 0:
        pats.append("Cardio-respiratory stress pattern (HR↑ + SpO₂↓)")
    if f.get("heart_rate", 0) > 0 and f.get("temperature", 0) > 0:
        pats.append("Thermal / physiological stress pattern (HR↑ + temperature↑)")
    if f.get("sleep_duration", 0) < 0 and f.get("fatigue", 0) > 0:
        pats.append("Sleep-debt / fatigue pattern (sleep↓ + fatigue↑)")
    return pd.DataFrame(rows), pats

# ============================== UI HELPERS ==============================
CSS = f"""
<style>
.stApp {{background: radial-gradient(1200px 600px at 80% -10%, #0f2a47 0%, #07111f 55%); color:{TEXT};
  font-family: "Segoe UI", system-ui, -apple-system, Roboto, "Helvetica Neue", Arial, sans-serif;}}
#MainMenu, footer {{visibility:hidden;}}
[data-testid="stSidebar"] {{background:#0b192a; border-right:1px solid #1c344c;}}
h1,h2,h3 {{color:#e7f4ff !important; letter-spacing:1px;}}
div.stButton > button {{background:#087e9b; color:#fff; border:none; border-radius:8px; font-weight:600; width:100%;}}
div.stButton > button:hover {{background:#09a4c5; color:#fff;}}
.hdr {{display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:14px;
  background:linear-gradient(110deg,#102943,#0a1728); border:1px solid #1e4963; border-radius:14px;
  padding:18px 24px; margin-bottom:14px;}}
.logo {{color:{CYAN}; font-size:30px; font-weight:800; letter-spacing:5px;}}
.sub {{color:#a9c2d7; font-size:11px; letter-spacing:2px; margin-top:2px;}}
.pill {{display:inline-block; padding:3px 10px; border-radius:20px; font-size:11px; font-weight:700;
  letter-spacing:1px; margin:2px 4px 2px 0; border:1px solid;}}
.live {{color:{GREEN}; border-color:{GREEN}; animation:blink 1.6s infinite;}}
.idle {{color:{AMBER}; border-color:{AMBER};}}
.sim {{color:{AMBER}; border-color:{AMBER}; background:rgba(255,176,32,.08);}}
.ok {{color:{CYAN}; border-color:{CYAN};}}
@keyframes blink {{50% {{opacity:.45;}}}}
.clock {{text-align:right; color:#a9c2d7; font-size:12px; line-height:1.7;}}
.clock b {{color:{TEXT}; font-size:15px;}}
.mc-card {{background:linear-gradient(135deg,#10243a,#0c1b2c); border:1px solid #1d405b; border-radius:12px;
  padding:14px 16px; height:100%;}}
.mc-label {{color:#7f9bb5; font-size:10px; letter-spacing:2px; font-weight:700;}}
.mc-value {{font-size:26px; font-weight:800; margin-top:4px;}}
.mc-sub {{color:#7f9bb5; font-size:11px;}}
.sec {{color:{CYAN}; font-size:12px; font-weight:800; letter-spacing:3px; margin:22px 0 8px;
  border-bottom:1px solid #1d3449; padding-bottom:6px;}}
.ac {{background:#0c1b2c; border:1px solid #1d405b; border-left:4px solid; border-radius:10px; padding:12px 14px;}}
.ac.sel {{box-shadow:0 0 0 1px {CYAN}, 0 0 18px rgba(61,217,240,.25);}}
.ac h4 {{margin:0 0 6px; color:{TEXT}; font-size:15px; letter-spacing:1px;}}
.kv {{display:flex; justify-content:space-between; font-size:12px; color:#8fa9c0; padding:1px 0;}}
.kv b {{font-size:13px;}} .kv i {{font-style:normal; color:#5f7a92; font-size:10px;}}
.alert {{background:#0c1b2c; border:1px solid #1d405b; border-left:5px solid; border-radius:10px; padding:12px 16px;}}
.sev {{font-weight:800; font-size:11px; letter-spacing:2px;}}
.tl {{display:flex; gap:12px; font-size:12px; padding:5px 0; border-bottom:1px solid #12283c; color:#a9bdd1;}}
.tl .t {{color:#5f7a92; min-width:140px;}} .tl .k {{min-width:90px; font-weight:800; letter-spacing:1px;}}
</style>
"""


def card(label, value, sub="", color=CYAN):
    return (f'<div class="mc-card"><div class="mc-label">{label}</div>'
            f'<div class="mc-value" style="color:{color}">{value}</div><div class="mc-sub">{sub}</div></div>')


def astro_card(c, selected):
    status, color = (("NO BASELINE", MUTED) if not c["z"] else status_of(c["worst"]))
    body = ""
    for col, (label, unit, dec, _) in INDICATORS.items():
        v = c["vals"].get(col)
        txt = "—" if v is None or pd.isna(v) else f"{v:.{dec}f}"
        vc = status_of(c["z"][col])[1] if col in c["z"] and abs(c["z"][col]) >= Z_WARN else TEXT
        body += f'<div class="kv"><span>{label}</span><b style="color:{vc}">{txt} <i>{unit}</i></b></div>'
    return (f'<div class="ac{" sel" if selected else ""}" style="border-left-color:{color}">'
            f'<h4>{html.escape(c["id"])} <span class="pill" style="color:{color};border-color:{color};'
            f'float:right">{status}</span></h4>{body}'
            f'<div class="mc-sub" style="margin-top:6px">Last reading: {c["last"] or "—"} UTC</div></div>')


def telemetry_chart(d, col, stats):
    label, unit, dec, _ = INDICATORS[col]
    s = d[["ts", col]].dropna()
    fig = go.Figure()
    if col in stats:
        m, sd = stats[col]
        fig.add_hrect(y0=m - Z_FLAG * sd, y1=m + Z_FLAG * sd, fillcolor="rgba(61,217,240,0.07)", line_width=0)
        fig.add_hline(y=m, line_dash="dot", line_color=CYAN, line_width=1,
                      annotation_text="personal baseline", annotation_font_size=10)
    fig.add_trace(go.Scatter(
        x=s["ts"], y=s[col], mode="lines", name=label, line=dict(color=CYAN, width=1.8),
        hovertemplate=f"%{{x|%d %b %H:%M:%S}}<br>{label}: %{{y:.{dec}f}} {unit}<extra></extra>"))
    if col in stats and not s.empty:
        out = s[(s[col] - m).abs() > Z_FLAG * sd]
        if not out.empty:
            fig.add_trace(go.Scatter(
                x=out["ts"], y=out[col], mode="markers", name="Anomaly",
                marker=dict(color=RED, size=8, line=dict(color="#fff", width=1)),
                hovertemplate=f"ANOMALY<br>%{{x|%d %b %H:%M:%S}}<br>{label}: %{{y:.{dec}f}} {unit}<extra></extra>"))
    fig.update_layout(template="plotly_dark", height=270, margin=dict(l=10, r=10, t=36, b=10),
                      title=dict(text=f"{label} ({unit})", font=dict(size=13, color=CYAN)),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(11,25,42,.8)",
                      showlegend=False, uirevision="keep", hovermode="x unified")
    fig.update_xaxes(gridcolor="#13293d")
    fig.update_yaxes(gridcolor="#13293d")
    return fig

# ============================== MISSION CONTROL VIEW (live fragment) ==============================


def mission_view(aid: str, source: str, range_label: str):
    ing = get_ingestor()
    now = datetime.now(timezone.utc)
    last = read_df("SELECT MAX(ts) m FROM telemetry")["m"][0]
    age = f"{int((now.replace(tzinfo=None) - pd.Timestamp(last).to_pydatetime()).total_seconds())}s ago" \
        if last and ing.running else (last or "—")

    # ---- A. header
    live = ('<span class="pill live">● LIVE MONITORING</span>' if ing.running
            else '<span class="pill idle">● MONITORING STANDBY</span>')
    link = ('<span class="pill ok">⬤ DATA LINK: SQLITE / INGEST THREAD OK</span>' if ing.thread.is_alive()
            else f'<span class="pill idle">⬤ INGEST THREAD DOWN</span>')
    st.markdown(
        f'<div class="hdr"><div><div class="logo">🚀 ASTRAWELL</div>'
        f'<div class="sub">AUTONOMOUS ASTRONAUT HEALTH INTELLIGENCE SYSTEM</div>'
        f'<div style="margin-top:8px">{live}{link}'
        f'<span class="pill sim">SIMULATION MODE — SIMULATED TELEMETRY, NOT REAL SENSOR DATA</span></div></div>'
        f'<div class="clock">SYSTEM TIME (UTC)<br><b>{now.strftime("%Y-%m-%d %H:%M:%S")}</b><br>'
        f'LAST TELEMETRY UPDATE<br><b>{last or "—"}</b> <span>({age})</span></div></div>',
        unsafe_allow_html=True)

    crew = crew_snapshot(source)
    if not crew:
        st.info("No telemetry yet. Start monitoring or import CSV data.")
        return

    # ---- B. mission statistics
    cutoff = (now - timedelta(seconds=max(30, 5 * ing.interval))).strftime(FMT)
    active = int(read_df("SELECT COUNT(DISTINCT astronaut_id) n FROM telemetry WHERE ts>=?",
                         (cutoff,))["n"][0]) if ing.running else 0
    n_anom = sum(1 for c in crew for z in c["z"].values() if abs(z) >= Z_FLAG)
    n_alerts = int(read_df("SELECT COUNT(*) n FROM live_alerts WHERE status='UNACKNOWLEDGED'")["n"][0])
    cols = st.columns(6)
    cards = [("ASTRONAUTS MONITORED", len(crew), "profiles in database", CYAN),
             ("ACTIVE SESSIONS", active, "receiving live data", GREEN if active else MUTED),
             ("TELEMETRY READINGS", f"{total_readings():,}", "stored, all sources", CYAN),
             ("ACTIVE ANOMALIES", n_anom, f"|z| ≥ {Z_FLAG} vs baseline", RED if n_anom else GREEN),
             ("ACTIVE ALERTS", n_alerts, "unacknowledged", RED if n_alerts else GREEN),
             ("SYSTEM STATUS", "OPERATIONAL" if ing.thread.is_alive() else "DEGRADED",
              "monitoring active" if ing.running else "standby",
              GREEN if ing.thread.is_alive() else AMBER)]
    for col, args in zip(cols, cards):
        col.markdown(card(*args), unsafe_allow_html=True)

    # ---- C. astronaut cards
    st.markdown('<div class="sec">ASTRONAUT MONITORING</div>', unsafe_allow_html=True)
    visible_crew = ([c for c in crew if c["id"] == aid]
                    if ing.monitor_mode == "Individual astronaut" else crew)
    per_row = 4 if ing.monitor_mode != "Individual astronaut" else 1
    for i in range(0, len(visible_crew), per_row):
        row = st.columns(per_row)
        for col, c in zip(row, visible_crew[i:i + per_row]):
            col.markdown(astro_card(c, c["id"] == aid), unsafe_allow_html=True)
    st.caption("Individual mode ingests and displays only the selected astronaut. Crew mode monitors all available astronauts concurrently.")

    # ---- D. telemetry charts
    st.markdown(f'<div class="sec">REAL-TIME TELEMETRY — {html.escape(aid)} — {range_label.upper()} '
                f'(ending at latest reading)</div>', unsafe_allow_html=True)
    d = load_window(aid, source, LIVE_RANGES.get(range_label, RANGES[range_label]))
    stats = baseline_stats(aid, source)
    if d.empty:
        st.info("No readings for this selection.")
        return
    keys = list(INDICATORS)
    for i in range(0, len(keys), 2):
        row = st.columns(2)
        for col, k in zip(row, keys[i:i + 2]):
            col.plotly_chart(telemetry_chart(d, k, stats), key=f"chart_{k}")

    # ---- E. health intelligence
    st.markdown('<div class="sec">HEALTH INTELLIGENCE</div>', unsafe_allow_html=True)
    snap = next(c for c in crew if c["id"] == aid)
    table, patterns = intelligence(snap["vals"], stats, d)
    if table.empty:
        st.caption("Not enough history to establish a personal baseline.")
    else:
        st.dataframe(table, hide_index=True)
        for p in patterns:
            st.warning(p + "  — pattern flag for review, not a diagnosis.")
        if not patterns:
            st.success("No multi-indicator pattern detected.")

    # ---- F. alert centre
    st.markdown('<div class="sec">ACTIVE ALERT CENTRE</div>', unsafe_allow_html=True)
    if source == "all":
        alerts = read_df("SELECT * FROM live_alerts ORDER BY (status='UNACKNOWLEDGED') DESC, detected_at DESC LIMIT 15")
    elif source == "csv_import":
        alerts = read_df("SELECT * FROM live_alerts WHERE source IN ('csv_import','csv_historical','csv_new') "
                         "ORDER BY (status='UNACKNOWLEDGED') DESC, detected_at DESC LIMIT 15")
    else:
        alerts = read_df("SELECT * FROM live_alerts WHERE source=? ORDER BY (status='UNACKNOWLEDGED') DESC, detected_at DESC LIMIT 15",
                         (source,))
    if alerts.empty:
        st.success("No alerts generated.")
    for r in alerts.to_dict("records"):
        color = sev_color(r["severity"])
        left, right = st.columns([5, 1])
        left.markdown(
            f'<div class="alert" style="border-left-color:{color}">'
            f'<span class="sev" style="color:{color}">{html.escape(str(r["severity"]).upper())}</span> '
            f'&nbsp; <b>{r["alert_id"]}</b> &nbsp;|&nbsp; {html.escape(r["astronaut_id"])} &nbsp;|&nbsp; '
            f'{r["detected_at"]} UTC &nbsp;|&nbsp; <span class="pill" style="color:'
            f'{GREEN if r["status"] == "ACKNOWLEDGED" else AMBER};border-color:'
            f'{GREEN if r["status"] == "ACKNOWLEDGED" else AMBER}">{r["status"]}</span>'
            f'<div class="mc-sub" style="margin-top:6px">Indicators: <b>{html.escape(r["indicators"] or "—")}</b> '
            f'({r["source"]})</div>'
            f'<div style="margin-top:4px;color:#c8d8e8;font-size:13px">{html.escape(r["summary"] or "")}</div>'
            f'<div style="margin-top:4px;color:{CYAN};font-size:12px">▶ {html.escape(r["action"] or "")}</div></div>',
            unsafe_allow_html=True)
        if r["status"] == "UNACKNOWLEDGED":
            right.button("ACKNOWLEDGE", key=f"ack_{r['alert_id']}", on_click=ack_alert, args=(r["alert_id"],))

    # ---- G. timeline
    st.markdown('<div class="sec">MISSION ACTIVITY TIMELINE</div>', unsafe_allow_html=True)
    ev = read_df("SELECT * FROM events ORDER BY id DESC LIMIT 14")
    st.markdown("".join(
        f'<div class="tl"><span class="t">{e["ts"]}</span>'
        f'<span class="k" style="color:{KIND_COLOR.get(e["kind"], CYAN)}">{e["kind"]}</span>'
        f'<span>{html.escape(str(e["astronaut_id"]))} — {html.escape(str(e["message"]))}</span></div>'
        for e in ev.to_dict("records")) or '<div class="mc-sub">No events yet.</div>',
        unsafe_allow_html=True)

# ============================== CSV ANALYSIS (existing workflow, preserved) ==============================



def process_csv_replay_timestamp(timestamp):
    """Run imported records at one original timestamp through the anomaly/alert pipeline."""
    rows = read_df(
        "SELECT * FROM telemetry WHERE ts=? AND source IN ('csv_new','csv_import') ORDER BY astronaut_id",
        (timestamp,),
    )
    for _, row in rows.iterrows():
        aid = str(row["astronaut_id"])
        history = read_df(
            "SELECT * FROM telemetry WHERE astronaut_id=? AND source IN ('csv_historical','csv_import') "
            "ORDER BY ts DESC LIMIT 2000", (aid,),
        )
        if history.empty:
            baseline = provisional_baseline([aid])
        else:
            baseline = calculate_baseline(to_long(history))
        current = to_long(pd.DataFrame([row]))
        anomalies = detect_anomalies(current, baseline)
        alerts = generate_alerts(evaluate_health_patterns(anomalies), anomalies)
        ingest_alerts(alerts, "csv_replay", aid, timestamp)


def create_csv_replay(speed=1.0):
    timestamps = read_df(
        "SELECT DISTINCT ts FROM telemetry WHERE source IN ('csv_new','csv_import') ORDER BY ts"
    )["ts"].astype(str).tolist()
    return ReplayController(timestamps, process_csv_replay_timestamp, speed=speed)


def provisional_baseline(astronaut_ids):
    """Transparent engineering reference baseline used only when no history was uploaded."""
    references = {
        "heart_rate": (75.0, 15.0, 1.0, 250.0),
        "spo2": (97.0, 1.5, 0.0, 100.0),
        "temperature": (36.8, 0.4, 25.0, 45.0),
        "sleep_duration": (7.0, 1.5, 0.0, 24.0),
        "fatigue": (2.0, 1.0, 1.0, 5.0),
    }
    rows = []
    for aid in sorted(set(astronaut_ids)):
        for indicator, (mean, std, minimum, maximum) in references.items():
            rows.append({"astronaut_id": aid, "indicator": indicator, "mean": mean,
                         "std": std, "minimum": minimum, "maximum": maximum, "count": 2})
    return pd.DataFrame(rows)


def _hash_upload(upload):
    digest = hashlib.sha256()
    upload.seek(0)
    while True:
        block = upload.read(1024 * 1024)
        if not block:
            break
        digest.update(block)
    upload.seek(0)
    return digest.digest()


def _iter_validated_upload(upload, label, chunksize=20000):
    """Read CSV in bounded chunks; wide rows expand to at most five long rows each."""
    upload.seek(0)
    try:
        chunks = pd.read_csv(upload, chunksize=chunksize)
        seen_keys = set()
        total = 0
        for raw_chunk in chunks:
            canonical = prepare_telemetry_csv(raw_chunk)
            canonical = validate_telemetry_chunk(canonical, label)
            total += len(canonical)
            yield canonical
        if total == 0:
            raise ValueError(f"{label}: the CSV contains no telemetry rows.")
    except pd.errors.EmptyDataError as exc:
        raise ValueError(f"{label}: the CSV is empty.") from exc
    finally:
        upload.seek(0)


def _baseline_from_aggregates(aggregates):
    rows = []
    for (aid, indicator), values in aggregates.items():
        count, total, total_sq, minimum, maximum = values
        mean = total / count
        variance = max((total_sq - count * mean * mean) / max(count - 1, 1), 0.0)
        rows.append({"astronaut_id": aid, "indicator": indicator, "mean": mean,
                     "std": variance ** 0.5, "minimum": minimum, "maximum": maximum, "count": count})
    return pd.DataFrame(rows, columns=[
        "astronaut_id", "indicator", "mean", "std", "minimum", "maximum", "count"
    ])


def run_csv_analysis(hf, nf):
    """Chunked historical/new CSV analysis; memory use is bounded by chunksize."""
    if hf is None and nf is None:
        return None, ["Upload historical data, new readings, or both."]
    try:
        hash_h = _hash_upload(hf) if hf is not None else b""
        hash_n = _hash_upload(nf) if nf is not None else b""
        aggregates = {}
        historical_ids = set()
        historical_sample = []
        if hf is not None:
            for chunk in _iter_validated_upload(hf, "Historical dataset"):
                for (aid, indicator), group in chunk.groupby(["astronaut_id", "indicator"]):
                    values = group["value"].astype(float)
                    key = (str(aid), str(indicator))
                    current = aggregates.get(key, [0, 0.0, 0.0, float("inf"), float("-inf")])
                    aggregates[key] = [
                        current[0] + len(values), current[1] + float(values.sum()),
                        current[2] + float((values * values).sum()),
                        min(current[3], float(values.min())), max(current[4], float(values.max()))
                    ]
                    historical_ids.add(str(aid))
                import_long_frame(chunk, f"Historical CSV '{hf.name}' chunk", source="csv_historical")
                if len(historical_sample) < 5000:
                    historical_sample.append(chunk.head(5000 - len(historical_sample)))
            baseline = _baseline_from_aggregates(aggregates)
            baseline_source = "Uploaded historical dataset (chunked)"
        else:
            baseline = None
            baseline_source = "Provisional engineering references — no historical dataset uploaded"

        alerts, explanations, anomaly_samples, new_ids = [], [], [], set()
        if nf is not None:
            for chunk in _iter_validated_upload(nf, "New readings dataset"):
                new_ids.update(chunk["astronaut_id"].astype(str).unique())
                if baseline is None:
                    active_baseline = provisional_baseline(chunk["astronaut_id"].unique())
                else:
                    known_ids = set(baseline["astronaut_id"].astype(str))
                    missing_ids = set(chunk["astronaut_id"].astype(str)) - known_ids
                    fallback = provisional_baseline(missing_ids) if missing_ids else pd.DataFrame()
                    active_baseline = pd.concat([baseline, fallback], ignore_index=True)
                anomalies = detect_anomalies(chunk, active_baseline)
                if not anomalies.empty:
                    if len(anomaly_samples) < 10000:
                        anomaly_samples.append(anomalies.head(10000 - len(anomaly_samples)))
                    generated = generate_alerts(evaluate_health_patterns(anomalies), anomalies)
                    alerts.extend(generated)
                    explanations.extend(explain_alert(a) for a in generated)
                import_long_frame(chunk, f"New readings CSV '{nf.name}' chunk", source="csv_new")

        if baseline is None:
            baseline = provisional_baseline(new_ids)
        combined_hash = hashlib.sha256(hash_h + b"::ASTRAWELL::" + hash_n).hexdigest()
        register_import(combined_hash, hf.name if hf is not None else nf.name)
        if alerts:
            reference_time = max(str(a.get("timestamp", "")) for a in alerts)
            ingest_alerts(alerts, "csv_import", "UNKNOWN", reference_time or now_ts())
            save_alerts(alerts[:1000])
        log_event("ANALYSIS", "—",
                  f"Chunked CSV analysis complete ({baseline_source}): {len(alerts)} alert(s)")
        sample_frames = anomaly_samples or historical_sample
        readings_preview = pd.concat(sample_frames, ignore_index=True) if sample_frames else pd.DataFrame()
        anomaly_frame = pd.concat(anomaly_samples, ignore_index=True) if anomaly_samples else pd.DataFrame()
        return {"baseline": baseline, "baseline_source": baseline_source,
                "anomalies": anomaly_frame, "alerts": alerts,
                "explanations": explanations[:200], "readings": readings_preview}, []
    except Exception as exc:
        return None, [str(exc)]

# ============================== APP ==============================


st.set_page_config(page_title="ASTRAWELL | Mission Control", page_icon="🚀", layout="wide",
                   initial_sidebar_state="expanded")
st.markdown(CSS, unsafe_allow_html=True)
initialize_database()
ing = get_ingestor()

with st.sidebar:
    st.markdown("## 🚀 MISSION CONTROL")
    st.caption("ASTRAWELL HEALTH INTELLIGENCE")
    st.markdown("### LIVE MONITORING")
    st.caption("⚠ Simulated telemetry. Start/Stop and interval apply to ALL open sessions.")
    b1, b2 = st.columns(2)
    b1.button("▶ START", on_click=ing.start, disabled=ing.running)
    b2.button("■ STOP", on_click=ing.stop, disabled=not ing.running)
    interval = st.slider("Telemetry sampling interval (seconds)", 1, 30, int(ing.interval),
                         help="At 1 second, one fresh reading is generated per monitored astronaut every second.")
    ing.interval = float(interval)
    st.divider()
    st.markdown("### CSV REPLAY")
    replay = st.session_state.get("csv_replay")
    if st.button("PREPARE / RESET CSV REPLAY", key="prepare_csv_replay"):
        st.session_state["csv_replay"] = create_csv_replay(
            st.session_state.get("csv_replay_speed", 1.0)
        )
        replay = st.session_state["csv_replay"]
    replay_speed = st.selectbox("CSV playback speed", [1, 2, 5, 10, 60], index=0,
                                format_func=lambda x: f"{x}x", key="csv_replay_speed")
    if replay is not None:
        replay.set_speed(replay_speed)
        rc1, rc2 = st.columns(2)
        rc1.button("▶ PLAY / RESUME", key="csv_replay_start", on_click=replay.resume)
        rc2.button("Ⅱ PAUSE", key="csv_replay_pause", on_click=replay.pause)
        rc3, rc4 = st.columns(2)
        rc3.button("■ STOP", key="csv_replay_stop", on_click=replay.stop)
        rc4.button("↺ RESET", key="csv_replay_reset", on_click=replay.reset)
        st.caption(f"Replay: {replay.status} · {replay.index:,}/{len(replay.timestamps):,} timestamps")
        st.progress(replay.progress)
        if replay.current_timestamp:
            st.caption(f"Source timestamp: {replay.current_timestamp} UTC")
        if replay.last_error:
            st.error(replay.last_error)

    st.divider()
    st.markdown("### VIEW")
    source_key = SOURCES[st.selectbox("Data source", list(SOURCES), index=2, help="Simulated and CSV data stay separate by default. Choose All sources only when you intentionally want to combine them.")]
    ids = list_astronauts(source_key)
    monitor_mode = st.radio("Monitoring mode", ["Crew (all astronauts)", "Individual astronaut"],
                            horizontal=False, key="monitor_mode")
    sel = st.selectbox("Astronaut", ids, key=f"astronaut_selector_{source_key}") if ids else None
    ing.monitor_mode = monitor_mode
    ing.target_astronaut = sel if monitor_mode == "Individual astronaut" else None
    range_label = st.select_slider("Live monitoring window", list(LIVE_RANGES), value="5 minutes")
    st.divider()
    st.markdown("### DATA INPUT")
    hist_file = st.file_uploader("Historical baseline CSV", type=["csv"], key="historical")
    new_file = st.file_uploader("New health readings CSV", type=["csv"], key="new_readings")
    if st.button("ANALYSE / IMPORT TELEMETRY", disabled=hist_file is None and new_file is None):
        try:
            res, errs = run_csv_analysis(hist_file, new_file)
            if errs:
                for e in errs:
                    st.error(e)
            else:
                st.session_state["analysis"] = res
                baseline_stats.clear()
                total_readings.clear()
                st.success("Analysis complete; data imported.")
                st.rerun()
        except Exception as e:
            st.error(f"Analysis failed: {e}")

tab_mc, tab_data, tab_analytics, tab_sys = st.tabs(["MISSION CONTROL", "DATA & ANALYTICS", "ADVANCED ANALYTICS", "SYSTEM"])

with tab_mc:
    if sel is None:
        st.info("No data yet — press START to begin simulated monitoring or import CSV data.")
    # run_every is fixed at decoration time; widget changes trigger a full rerun that rebuilds it
    st.fragment(run_every=f"{interval}s")(mission_view)(sel or "", source_key, range_label) if sel else None

with tab_data:
    st.markdown("## CSV ANALYSIS RESULTS")
    res = st.session_state.get("analysis")
    if res is None:
        st.info("Upload historical data, new readings, or both in the sidebar, then press ANALYSE / IMPORT TELEMETRY.")
    else:
        st.markdown("### BASELINE")
        st.caption(res.get("baseline_source", "Baseline source not recorded"))
        st.dataframe(res["baseline"], hide_index=True)
        st.markdown("### READING COMPARISON")
        if not res["anomalies"].empty:
            st.dataframe(res["anomalies"], hide_index=True)
        else:
            st.caption("No separate new-readings file was uploaded. Historical data was imported for monitoring and analytics.")
        for ex in res["explanations"]:
            with st.expander(f"{str(ex['priority']).upper()} | {ex['alert_id']}"):
                st.write(ex["summary"])
                for dt in ex["details"]:
                    st.write(f"**{dt['indicator']}** — current {dt['current_value']} | "
                             f"baseline {dt['baseline_value']}")
                st.info(ex["recommended_action"])
    st.markdown("### STORED ALERT HISTORY (database/db.py)")
    hist = get_alert_history()
    st.dataframe(pd.DataFrame(hist), hide_index=True) if hist else st.caption("No stored alert history.")


with tab_analytics:
    st.markdown("## ADVANCED HEALTH ANALYTICS")
    st.caption("Descriptive and experimental decision-support outputs. Correlation is not causation; projections are not validated predictions.")
    analysis_ids = list_astronauts(source_key)
    if not analysis_ids:
        st.info("Start simulated monitoring or import CSV telemetry to populate analytics.")
    else:
        analysis_aid = st.selectbox("Select astronaut for individual analysis", analysis_ids,
                                    index=analysis_ids.index(sel) if sel in analysis_ids else 0,
                                    key="analytics_astronaut")
        selected_readings = load_window(analysis_aid, source_key, RANGES["30 days"])
        all_frames = []
        for crew_id in analysis_ids:
            frame = load_window(crew_id, source_key, RANGES["30 days"])
            if not frame.empty:
                all_frames.append(frame)
        combined = pd.concat(all_frames, ignore_index=True) if all_frames else pd.DataFrame()

        st.markdown("### CREW DETERIORATION COMPARISON — WHO IS CHANGING FASTEST?")
        deterioration = deterioration_comparison(combined)
        if deterioration.empty:
            st.info("Not enough timestamped history across the crew. Each astronaut needs at least six distinct days and multiple readings in the early and late portions of the window.")
        else:
            display_deterioration = deterioration.drop(columns=["_details"], errors="ignore")
            st.dataframe(display_deterioration, hide_index=True, use_container_width=True)
            st.caption("Ranked by adverse movement from the first third to the last third of each astronaut's own 30-day timeline. Higher heart rate/temperature/fatigue and lower SpO₂/sleep count as adverse. This experimental index is not a medical severity score.")
            with st.expander("WHY IS EACH ASTRONAUT RANKED HERE?"):
                for item in deterioration.to_dict("records"):
                    st.markdown(f"**#{item['Rank']} — {item['Astronaut']}**")
                    st.write(item["Main drivers"])
                    detail_rows = []
                    for indicator, values in item["_details"].items():
                        detail_rows.append({
                            "Indicator": indicator,
                            "Early-period mean": round(values["early_mean"], 3),
                            "Late-period mean": round(values["late_mean"], 3),
                            "Adverse shift (σ)": round(values["adverse_change_sigma"], 2),
                        })
                    if detail_rows:
                        st.dataframe(pd.DataFrame(detail_rows), hide_index=True, use_container_width=True)

        p1, p2, p3 = st.columns(3)
        with p1:
            period_choice = st.selectbox("Summary interval", ["Daily", "Weekly", "Monthly"], key="summary_period")
        with p2:
            horizon = st.selectbox("Experimental estimate horizon", [3, 6, 12], index=1, format_func=lambda x: f"{x} readings")
        with p3:
            st.metric("Crew profiles with data", len(all_frames))

        period_code = {"Daily": "D", "Weekly": "W", "Monthly": "MS"}[period_choice]
        summary = period_summary(selected_readings, period_choice.lower())
        st.markdown(f"### {period_choice.upper()} SUMMARY — {html.escape(analysis_aid)}")
        if summary.empty:
            st.info("Not enough telemetry for a summary.")
        else:
            summary_view = summary.copy()
            summary_view["period"] = pd.to_datetime(summary_view["period"]).dt.strftime("%Y-%m-%d")
            display_cols = ["period", *INDICATORS, "reading_count"]
            st.dataframe(summary_view[[c for c in display_cols if c in summary_view]], hide_index=True, use_container_width=True)
            st.download_button("DOWNLOAD SUMMARY CSV", summary_view.to_csv(index=False).encode("utf-8"),
                               file_name=f"astrawell_{analysis_aid}_{period_choice.lower()}_summary.csv", mime="text/csv")

        st.markdown("### CREW COMPARISON — EACH ASTRONAUT VS THEIR OWN BASELINE")
        comparison = crew_comparison(combined)
        if comparison.empty:
            st.info("Crew comparison requires at least five readings per indicator.")
        else:
            comp_cols = ["Astronaut", "Readings", *[f"{c}_current" for c in INDICATORS], *[f"{c}_z" for c in INDICATORS]]
            st.dataframe(comparison[[c for c in comp_cols if c in comparison]], hide_index=True, use_container_width=True)
            st.caption("Each z-score compares the latest value with that astronaut’s own historical mean and standard deviation. It is not a medical risk score.")

        st.markdown("### MULTI-INDICATOR CORRELATION")
        corr = indicator_correlations(selected_readings)
        if corr.empty:
            st.info("Not enough overlapping telemetry to calculate correlations.")
        else:
            st.dataframe(corr.round(2), use_container_width=True)
            fig_corr = go.Figure(data=go.Heatmap(z=corr.values, x=corr.columns, y=corr.index,
                                                  zmin=-1, zmax=1, colorscale="RdBu", text=corr.round(2).values,
                                                  texttemplate="%{text}"))
            fig_corr.update_layout(template="plotly_dark", height=390, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig_corr, use_container_width=True, key="correlation_heatmap")

        st.markdown(f"### EXPERIMENTAL TREND ESTIMATES — NEXT {horizon} READINGS")
        estimates = trend_projection(selected_readings, steps=int(horizon))
        if estimates.empty:
            st.info("At least six timestamped readings per indicator are needed for a trend estimate.")
        else:
            st.dataframe(estimates.round(3), hide_index=True, use_container_width=True)
            st.warning("These values are simple linear extrapolations of recent data. They are not clinically validated forecasts and should not guide treatment or mission decisions without approved review.")

        st.markdown("### EXPORT ASTRONAUT REPORT")
        pdf_bytes = report_pdf(build_report(selected_readings, analysis_aid), title=f"ASTRAWELL Health Report — {analysis_aid}")
        st.download_button("DOWNLOAD PDF HEALTH REPORT", pdf_bytes,
                           file_name=f"ASTRAWELL_{analysis_aid}_health_report.pdf", mime="application/pdf")
        st.download_button("DOWNLOAD SELECTED TELEMETRY CSV", selected_readings.to_csv(index=False).encode("utf-8"),
                           file_name=f"ASTRAWELL_{analysis_aid}_telemetry.csv", mime="text/csv")

with tab_sys:
    st.markdown("## SYSTEM INFORMATION")
    counts = read_df("SELECT source, COUNT(*) readings, COUNT(DISTINCT astronaut_id) astronauts, "
                     "MIN(ts) first_reading, MAX(ts) last_reading FROM telemetry GROUP BY source")
    st.dataframe(counts, hide_index=True)
    st.write(f"Live DB: `{DB_PATH}` (SQLite, WAL) · Ingest source: `{ing.source.name}` · "
             f"Ticks this process: {ing.ticks} · Thread alive: {ing.thread.is_alive()}")
    if ing.last_error:
        st.error(f"Last pipeline/ingest error: {ing.last_error}")
    st.markdown("""
**Architecture** — Streamlit UI · single shared ingest thread (`Ingestor`) · pluggable `TelemetrySource`
(replace `SimulatedSource` with a real sensor/API reader) · SQLite with idempotent inserts ·
existing ASTRAWELL analytics/decision-support modules.

**Anomaly markers** on charts use |z| ≥ 2.5 against the personal baseline (SQL-aggregated mean/std).
The alert pipeline (`detect_anomalies` → `evaluate_health_patterns` → `generate_alerts`) runs on a rolling
30-reading window every 5 ticks; alerts are de-duplicated per astronaut/indicator-set/30-minute bucket.
""")
    st.caption("Research prototype. Not a validated medical device. Simulated telemetry is not real astronaut data.")