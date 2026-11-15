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
The normalized long-format CSV requires these columns:
`astronaut_id,timestamp,indicator,value,unit,source`

Supported indicators and units:
- `heart_rate` — `bpm`
- `spo2` — `percent`
- `temperature` — `C`
- `sleep_duration` — `hours`
- `fatigue` — `score`

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
