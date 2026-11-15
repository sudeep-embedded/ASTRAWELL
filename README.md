# ASTRAWELL
**Autonomous Astronaut Health Intelligence and Decision Support System**

ASTRAWELL is an offline-first research prototype for reviewing astronaut health telemetry, comparing measurements with personal baselines, highlighting unusual multi-indicator patterns, and producing descriptive reports.

> **Important:** The bundled live feed is synthetic demonstration telemetry. CSV data is user-supplied. This project is not a medical device, does not diagnose, and does not prescribe treatment. Thresholds and trend projections are not clinically validated.

## Features
- Streamlit Mission Control dashboard with simulated multi-crew telemetry.
- Local SQLite storage for telemetry, events, imports, and alerts.
- CSV ingestion, validation, normalization, baseline calculation, and anomaly review.
- Personal-baseline deviation indicators and explainable pattern flags.
- Daily, weekly, and monthly descriptive summaries.
- Crew comparison using latest measurements and per-crew z-scores.
- Pearson correlation matrix for available indicators.
- Experimental short-horizon linear trend extrapolation (not a validated prediction).
- Downloadable PDF report and CSV analytics exports.

## Requirements
- Python 3.10+
- Dependencies in `requirements.txt`

## Windows PowerShell setup
```powershell
git clone https://github.com/sudeep-embedded/ASTRAWELL.git
cd ASTRAWELL
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Run locally
```powershell
streamlit run app.py
```
Open the local URL printed by Streamlit (normally http://localhost:8501).

## Run tests
```powershell
python -m pytest -q
```

## CSV schema
ASTRAWELL accepts either of these input layouts:

**Long format**
`astronaut_id,timestamp,indicator,value,unit,source`

**Wide format**
`astronaut_id,timestamp,heart_rate_bpm,spo2_percent,temperature_C,sleep_duration_hours,fatigue_score`

For wide files, `source` is optional. The importer converts each populated measurement column into the canonical long format. Partial wide files are accepted when they contain at least one supported measurement column.

Upload a historical baseline file, a new-readings file, or both. If only new readings are supplied, the application labels the comparison reference as provisional; it is not a personalized historical baseline. When both files are supplied, the new readings are compared with the historical baseline only.

Supported indicators and units:
- `heart_rate` — `bpm`
- `spo2` — `percent`
- `temperature` — `C`
- `sleep_duration` — `hours`
- `fatigue` — `score`

The astronaut selector is populated from distinct IDs currently stored for the selected data source, rather than a fixed crew count. Imported historical and new-reading records are stored separately so historical baselines can be preferred during dashboard comparison.

**Current limitation:** uploaded CSV files are imported and analysed, but timestamp-paced Start/Pause/Resume/Stop/Reset CSV replay is not yet implemented. The live sampling slider controls synthetic telemetry generation and dashboard refresh, not uploaded-file playback.

Input validation bounds are data-quality checks, not medical safety limits.

## Storage and deployment notes
- The application stores live dashboard telemetry in `data/astrawell_live.db` and legacy CSV workflow records in `database/astrawell.db`.
- SQLite is suitable for a local demo and small single-instance deployment. Ephemeral cloud filesystems may reset on restart; use persistent storage before relying on historical records.
- The simulator and its start/stop control are shared across sessions in one Streamlit process. This prototype has no authentication or per-user data isolation.
- Do not upload real astronaut or other sensitive health data to a public demo.

## Project structure
```text
analytics/          Baselines, anomaly detection, rule engine, extended analytics
database/           SQLite persistence
decision_support/   Alert generation and explanations
ingestion/          CSV/JSON ingestion helpers
preprocessing/      Validation and normalization
app.py              Streamlit Mission Control application
tests/              Automated analytics tests
```

## Research limitations
The application uses simulated telemetry and simple statistical methods. Pearson correlation does not establish causation. Linear extrapolation assumes recent trends continue and can fail abruptly. Outputs are intended for demonstration and human review only; they must not replace approved onboard medical procedures.
