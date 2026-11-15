# ASTRAWELL

**Autonomous Astronaut Health Intelligence and Decision Support System**

ASTRAWELL is a Streamlit research prototype for ingesting, inspecting, and analysing astronaut-style health telemetry. It combines a synthetic monitoring feed, CSV-based historical/new-reading workflows, personal-baseline comparisons, anomaly screening, explainable alert patterns, crew analytics, and downloadable reports.

> **Research and safety boundary:** The built-in telemetry generator and the example datasets created for development are synthetic. They are not NASA telemetry, astronaut medical records, or clinically validated reference data. ASTRAWELL is not a medical device, does not diagnose, and must not be used to make treatment or mission-safety decisions.

## 1. What the application currently does

- Displays a Mission Control dashboard for astronaut profiles and telemetry.
- Generates synthetic telemetry for a 30-profile demo crew when live monitoring is started.
- Imports long- or wide-format CSV telemetry and validates its structure, units, timestamps, duplicates, and configured data-quality ranges.
- Supports separate historical-baseline and new-readings CSV uploads.
- Calculates baseline-relative deviations and applies the existing anomaly and rule/alert pipeline.
- Shows astronaut summaries, telemetry charts, health-intelligence indicators, alerts, and a mission activity timeline.
- Provides timestamp-based CSV replay controls (prepare, play/resume, pause, stop, reset) for imported replay records.
- Provides descriptive summaries, crew comparisons, correlations, experimental trend extrapolations, PDF reports, and CSV exports.
- Stores dashboard telemetry, alerts, and events in SQLite.

The project currently tracks five indicators: heart rate, SpO₂, body temperature, sleep duration, and fatigue. Blood pressure is **not** part of the current telemetry schema or supported CSV contract.

## 2. Repository layout

```text
ASTRAWELL/
├── analytics/          Baseline, anomaly, rule, and mission analytics
├── config/              Configuration modules
├── dashboard/           Dashboard-related modules
├── data/                Runtime SQLite data (not source datasets)
├── database/            Database persistence helpers
├── decision_support/    Alert generation and explanations
├── ingestion/           CSV ingestion and replay controller
├── preprocessing/       Validation and normalization
├── tests/                Test package
├── app.py                Streamlit application entry point
├── requirements.txt      Python dependencies
└── README.md             Setup, operation, and data workflow
```

The Streamlit application is currently orchestrated from `app.py`; supporting modules provide ingestion, replay, analytics, persistence, validation, and decision-support functions.

## 3. Requirements

- Python 3.10 or newer (Python 3.11 is used in the development environment).
- Git.
- Dependencies listed in `requirements.txt`.

## 4. Windows PowerShell: clone and install

Open PowerShell:

```powershell
git clone https://github.com/sudeep-embedded/ASTRAWELL.git
cd ASTRAWELL

python -m venv venv
.\venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks virtual-environment activation, use the current-user execution-policy guidance from Microsoft, or run the environment's Python executable directly:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m streamlit run app.py
```

## 5. Run ASTRAWELL locally

With the virtual environment active:

```powershell
streamlit run app.py
```

Open the local URL printed in the terminal, normally `http://localhost:8501`. Keep the terminal running while using the dashboard. Stop the local server with `Ctrl+C`.

## 6. Mission Control workflow

### 6.1 Synthetic live monitoring

1. Open the **Mission Control** tab.
2. Select a data source and crew/individual monitoring view in the sidebar.
3. Set the telemetry sampling interval.
4. Press **START** to begin the synthetic feed.
5. Watch the crew cards, telemetry charts, anomaly indicators, alert centre, and activity timeline.
6. Press **STOP** to stop the feed while retaining the stored readings.
7. Press **RESET** to stop monitoring and clear the simulated live-session telemetry and simulated live alerts. CSV-imported data and CSV-origin alerts are preserved.

Starting a new synthetic monitoring session also initializes a fresh simulated session. The live generator is illustrative and does not connect to spacecraft sensors.

### 6.2 CSV upload and analysis

1. Prepare a historical CSV and/or a new-readings CSV using one of the supported schemas below.
2. In the sidebar, upload the historical file in **Historical baseline CSV** (if available).
3. Upload the new file in **New health readings CSV**.
4. Press **ANALYSE / IMPORT TELEMETRY**.
5. Open **Data & Analytics** to inspect the baseline, astronaut condition summary, reading comparisons, and alert explanations.
6. Return to Mission Control and select **CSV import** when you want to isolate imported records from synthetic telemetry.

When a historical file is supplied, its records are used to establish astronaut-specific historical references and the new readings are assessed against those references. If no historical file is supplied, the analysis uses clearly labelled provisional engineering references; those are not personal baselines.

### 6.3 CSV replay

After a new-readings file has been imported:

1. Choose **CSV import** as the Mission Control data source to isolate the replay data.
2. Choose the astronaut and monitoring view.
3. Press **PREPARE / RESET CSV REPLAY**.
4. Choose a playback speed (1x, 2x, 5x, 10x, or 60x).
5. Press **PLAY / RESUME**.
6. Use **PAUSE**, **STOP**, and **RESET VALUES** to control the replay cursor.
7. Observe the chart and astronaut values as the replay cursor advances.

Replay uses the timestamps stored with imported CSV rows. It does not change the original CSV timestamps. A replay reset returns the display cursor to the first replay timestamp; it does not delete imported records.

## 7. CSV input contract

ASTRAWELL supports two layouts.

### 7.1 Wide format

One row per astronaut and timestamp, with one or more supported measurement columns:

```csv
astronaut_id,timestamp,heart_rate_bpm,spo2_percent,temperature_C,sleep_duration_hours,fatigue_score
AST001,2026-01-01T00:00:00Z,72,98.1,36.7,7.2,2
```

Required identity columns:
- `astronaut_id`
- `timestamp`

At least one supported measurement column is required. The supported columns are:

| CSV column | Canonical indicator | Unit |
|---|---|---|
| `heart_rate_bpm` | `heart_rate` | `bpm` |
| `spo2_percent` | `spo2` | `percent` |
| `temperature_C` | `temperature` | `C` |
| `sleep_duration_hours` | `sleep_duration` | `hours` |
| `fatigue_score` | `fatigue` | `score` |

### 7.2 Long format

One row per indicator measurement:

```csv
astronaut_id,timestamp,indicator,value,unit,source
AST001,2026-01-01T00:00:00Z,heart_rate,72,bpm,csv_import
AST001,2026-01-01T00:00:00Z,spo2,98.1,percent,csv_import
```

The importer normalizes both layouts to a canonical long format. Timestamps are parsed as UTC. Unsupported indicators, invalid/missing required values, unit mismatches, configured out-of-range values, and duplicate astronaut/timestamp/indicator records are rejected.

Configured ingestion bounds are **data-quality validation limits only**. They are not medical reference ranges or safety thresholds.

## 8. Analysis and alerting concepts

- **Personal baseline:** indicator-level historical reference values for an astronaut when sufficient historical records exist.
- **Deviation:** current readings are compared with the applicable baseline using standardized deviations (z-scores).
- **Status thresholds:** the dashboard uses configurable watch/flag thresholds (currently `Z_WARN = 1.5` and `Z_FLAG = 2.5`) for visualization and screening.
- **Anomaly pipeline:** `detect_anomalies` → `evaluate_health_patterns` → `generate_alerts` → alert persistence/explanation.
- **Crew comparison:** compares current values with each astronaut's available historical statistics.
- **Correlation:** Pearson correlation summarizes linear association; it does not establish causation.
- **Trend estimates:** simple linear extrapolations of recent readings; they are experimental and not validated forecasts.

These calculations are engineering demonstrations. Their thresholds and outputs have not been validated for astronaut clinical use.

## 9. Dashboard sections

| Section | Purpose |
|---|---|
| Mission Control | Monitoring state, crew cards, live charts, health intelligence, alerts, activity timeline |
| Data & Analytics | CSV analysis results, baseline table, astronaut condition summary, alert explanations, stored alert history |
| Advanced Analytics | Period summaries, crew comparison, deterioration comparison, correlation, experimental trend estimates, PDF/CSV exports |
| System | Source-level database counts, ingest-thread status, architecture notes, error visibility |

## 10. Storage and reset behavior

The application uses SQLite for dashboard telemetry and supporting event/alert data. The live dashboard database is configured at `data/astrawell_live.db`; supporting legacy database helpers are in `database/`.

- Synthetic live telemetry is tagged separately from imported CSV records.
- Historical and new CSV imports are stored with distinct source labels so they can be selected and analysed separately.
- **STOP** stops the synthetic generator; it does not delete stored readings.
- **RESET** clears only the simulated live-session telemetry and simulated live alerts. It preserves CSV-imported telemetry, CSV-origin alerts, the separate stored alert history, and the event timeline.
- **CSV replay RESET VALUES** changes the replay cursor; it does not delete imported telemetry.

SQLite persistence on a cloud host depends on the deployment filesystem. If the host uses ephemeral storage, database contents may be lost on restart or redeploy. Use a persistent database/storage service before relying on long-term records.

## 11. Tests and local verification

Install the dependencies, activate the virtual environment, then run:

```powershell
python -m pytest -q
```

For a focused test file:

```powershell
python -m pytest test_baseline.py -q
```

A passing test suite does not replace manual verification of Streamlit interactions or deployed cloud behavior. Record separately:
- automated test result,
- local browser test result,
- deployed Streamlit test result.

Do not report an interaction as verified unless it was actually exercised.

## 12. Deployment overview

The app is designed to run with Streamlit:

1. Push the application and dependency files to the GitHub repository.
2. Configure Streamlit Community Cloud to deploy the repository's `main` branch with `app.py` as the entry point.
3. Ensure `requirements.txt` contains all runtime dependencies.
4. Review deployment logs after each update.
5. Open the deployed URL and test the affected workflow in the browser.

A successful GitHub merge means the source code is on `main`; it does not by itself prove that Streamlit deployed successfully or that the browser workflow works.

## 13. Contribution and Git workflow

Use a separate branch for each focused change:

```powershell
git checkout main
git pull origin main
git checkout -b fix/short-description

# edit and test only the intended scope
git status
git diff
git add app.py
git commit -m "Describe the focused change"
git push -u origin fix/short-description
```

Open a pull request from the feature branch to `main`. Review the changed files and diff, check mergeability and available checks, then merge. Do not force a merge when GitHub reports conflicts or required checks fail. After merging, pull `main` locally and verify deployment separately.

## 14. Current scope and known gaps

- The current supported indicators are heart rate, SpO₂, temperature, sleep duration, and fatigue. Blood pressure is not implemented in the current schema.
- The current project is a prototype, not a validated clinical decision-support product.
- The built-in generator is synthetic; no real spacecraft sensor integration is present.
- No NASA source package or official NASA requirements document has been incorporated into this repository review. NASA-specific compliance, data provenance, and requirement traceability must remain pending until the relevant NASA material is supplied and reviewed.
- Authentication, role-based access, audit-grade security, multi-user data isolation, and a production-grade persistent data store are not implemented.
- Cloud deployment and local development may behave differently because of process lifetime, caching, and filesystem persistence.

## 15. Project intent

The development objective is to build a transparent demonstration pipeline:

**Telemetry input → validation → normalization → persistence → baseline comparison → anomaly screening → explainable alerts → visualization and reports.**

The next engineering step for any NASA-provided dataset is to inspect its provenance, license, schema, units, timestamps, missingness, and documented interpretation before mapping it into ASTRAWELL. Do not assume that NASA data columns are interchangeable with the current synthetic indicators.
