# ASTRAWELL — Project Technical Report

**Project title:** Autonomous Astronaut Health Intelligence and Decision Support System  
**Repository:** https://github.com/sudeep-embedded/ASTRAWELL  
**Application:** Streamlit Mission Control prototype  
**Report purpose:** Document the current project objective, implemented workflows, architecture, data handling, analytics, operational process, limitations, and next steps.

> **Evidence boundary:** This report is based on the repository implementation and project context available at the time of writing. No NASA source dataset, NASA technical specification, or official NASA requirement document was attached for this review. Therefore, this report describes ASTRAWELL as implemented; it does not claim NASA data integration, NASA endorsement, or compliance with NASA requirements.

---

## 1. Executive summary

ASTRAWELL is a research prototype intended to demonstrate how astronaut-style health telemetry can be ingested, validated, stored, compared against historical baselines, screened for unusual patterns, and presented through an operational dashboard.

The system currently combines:
- a synthetic telemetry generator for a 30-profile demonstration crew;
- CSV ingestion for historical and new health readings;
- baseline-relative statistical analysis;
- anomaly screening and rule-based alert generation;
- timestamp-based CSV replay;
- a Streamlit dashboard with crew cards, telemetry charts, alert details, and activity history;
- advanced descriptive analytics and report exports;
- SQLite persistence.

The central processing concept is:

**Input → validation → normalization → storage → baseline comparison → anomaly screening → alert/explanation → visualization/reporting.**

The prototype is useful for demonstrating software workflow and interface behavior. It is not a clinically validated system and does not connect to real astronaut sensors.

## 2. Problem framing and project objective

Long-duration human spaceflight creates a need to observe multiple health-related indicators over time and to identify changes that may warrant human review. A useful software demonstration should make data provenance visible, retain time-series history, compare an astronaut's current readings with an appropriate reference, and explain why a record or pattern was flagged.

ASTRAWELL's engineering objective is to demonstrate that end-to-end workflow with modular software components and reproducible input files.

The current implementation focuses on five data indicators:
1. Heart rate
2. Peripheral oxygen saturation (SpO₂)
3. Body temperature
4. Sleep duration
5. Fatigue score

Blood pressure is not currently represented in the application's telemetry schema, chart definitions, or CSV mapping. It must not be described as an implemented feature.

## 3. Intended users and system boundary

The prototype is designed for demonstration and technical review by project developers, evaluators, and users inspecting astronaut-style telemetry workflows.

The system boundary currently includes:
- locally generated synthetic telemetry;
- user-uploaded CSV data;
- data validation and normalization;
- local SQLite persistence;
- statistical and rule-based analysis;
- dashboard visualization and exports.

The boundary currently excludes:
- direct spacecraft sensor integration;
- authenticated operational interfaces;
- approved clinical decision-making;
- validated medical thresholds;
- certified medical-device functionality;
- verified NASA data integration.

## 4. Implemented functional capabilities

### 4.1 Synthetic live monitoring

The application includes a simulated source that generates readings for a deterministic set of 30 demo astronaut IDs. The generated measurements include variation and occasional multi-indicator anomaly episodes to exercise the dashboard and analysis pipeline.

The source is explicitly identified as simulated. It must not be confused with real-time sensor data.

The live monitoring controls include:
- **START:** starts a fresh simulated monitoring session;
- **STOP:** stops generation and retains the stored readings;
- **RESET:** stops generation and clears simulated live-session telemetry and simulated live alerts while preserving CSV-imported records and CSV-origin alerts.

### 4.2 CSV ingestion

The ingestion module accepts two layouts:

**Wide format:** one row per astronaut and timestamp, with columns such as `heart_rate_bpm`, `spo2_percent`, `temperature_C`, `sleep_duration_hours`, and `fatigue_score`.

**Long format:** one row per astronaut, timestamp, indicator, value, and unit.

The ingestion workflow:
1. reads the uploaded file in bounded chunks;
2. maps wide columns into canonical indicator names and units, or accepts canonical long format;
3. parses timestamps as UTC and numeric values;
4. validates required fields, supported indicators, units, configured data-quality bounds, and duplicate keys;
5. normalizes and stores the records;
6. reports analysis results and any validation errors.

The configured numeric bounds are data-quality checks. They are not medical reference limits.

### 4.3 Historical baseline and new-reading analysis

The CSV workflow can accept:
- historical baseline data only;
- new readings only;
- historical and new readings together.

When historical data is supplied, the application calculates astronaut/indicator reference statistics from the historical records and evaluates the new readings against those references.

When no historical data is supplied, the analysis can use provisional engineering reference values. The interface labels these as provisional and warns that they are not personal historical baselines.

The baseline comparison is a statistical screening mechanism. It does not establish medical health or disease status.

### 4.4 Anomaly and alert workflow

The application's decision-support path uses the existing analytics and decision-support modules:

1. normalized readings are passed to anomaly detection;
2. detected deviations are evaluated for multi-indicator health patterns;
3. rule evaluation results are passed to alert generation;
4. alert explanations are produced;
5. alerts are persisted and displayed for review.

The Mission Control dashboard currently uses watch and flag z-score thresholds configured in `app.py` (1.5 and 2.5 respectively). These are prototype configuration values, not validated clinical cut-offs.

### 4.5 CSV replay

The replay controller operates over an ordered list of timestamps. It supports:
- prepare/reset;
- play/resume;
- pause;
- stop;
- configurable playback speeds;
- a current replay timestamp and progress value.

The replay callback processes the imported readings at each timestamp. The Mission Control chart and summary queries can be capped at the replay cursor so that the dashboard reveals data progressively rather than immediately showing the end of the file.

Replay reset changes the display cursor; it does not delete the imported dataset.

### 4.6 Dashboard and analytics

The dashboard is divided into four main sections:

| Section | Implemented purpose |
|---|---|
| Mission Control | System state, crew cards, current readings, time-series charts, health intelligence, alerts, and activity timeline |
| Data & Analytics | Uploaded baseline, astronaut condition summary, new-reading comparisons, alert explanations, and stored alert history |
| Advanced Analytics | Period summaries, crew comparisons, deterioration comparisons, correlations, experimental trend estimates, PDF and CSV exports |
| System | Source-level telemetry counts, thread status, database information, and diagnostic messages |

Advanced analytics include descriptive statistics, per-astronaut comparisons, Pearson correlation, and simple linear trend extrapolation. Correlation does not establish causation, and linear extrapolation is not a validated forecast.

## 5. Technical architecture

### 5.1 Application layer

- `app.py` is the Streamlit entry point and orchestrates the dashboard, shared ingestion service, SQLite queries, chart generation, CSV workflow, and analytics presentation.
- Streamlit fragments refresh selected dashboard areas.
- Cached resources are used for the shared ingestion service; this requires care when code changes because cached objects can outlive a script rerun.

### 5.2 Ingestion and preprocessing

- `ingestion/telemetry_csv.py` maps supported CSV layouts into canonical long-format telemetry and validates the normalized rows.
- `ingestion/replay.py` provides timestamp-paced replay control.
- `preprocessing/validator.py` and `preprocessing/normalizer.py` provide validation and normalization support for the analytics pipeline.

### 5.3 Analytics

The analytics package includes baseline calculation, anomaly detection, rule evaluation, and mission-level analytics. The dashboard uses these modules to create baseline-relative comparisons, summaries, correlations, and trend estimates.

### 5.4 Decision support

The decision-support package generates alerts and explanatory content. Alerts are intended to direct attention to readings or patterns for human review, not to prescribe medical action.

### 5.5 Persistence

The application uses SQLite for telemetry and related state. The live dashboard database path is configured as `data/astrawell_live.db`. Supporting database modules are located in `database/`.

The schema includes:
- telemetry records with astronaut ID, timestamp, source, and indicator columns;
- live alerts with severity, indicator set, timestamp, explanation, action, and acknowledgement state;
- mission events;
- import-registration records.

Telemetry source labels distinguish simulated records from imported/replay records. Source separation is important for filtering, replay, and reset behavior.

## 6. Data model and provenance

The current wide telemetry record includes:
- `astronaut_id`
- `timestamp`
- `heart_rate`
- `spo2`
- `temperature`
- `sleep_duration`
- `fatigue`
- `source`

The CSV adapter maps external column names to canonical indicator names and units.

Source labels are used to distinguish simulated telemetry and imported datasets. The application supports source filtering so the user can isolate a CSV workflow from the synthetic live feed.

For any future NASA-provided data, provenance must be retained. At minimum, the project should document:
- original source and download location;
- dataset title and version;
- license or usage conditions;
- acquisition date;
- original field names and units;
- timestamp semantics and time zone;
- missing-value conventions;
- subject/participant identifiers and de-identification conditions;
- transformation steps and mapping decisions.

These NASA-specific metadata have not yet been reviewed because the source material has not been provided in this conversation.

## 7. Operational workflows

### Workflow A — Run synthetic monitoring

1. Start the Streamlit application.
2. Select the desired source and crew/individual view.
3. Set the sampling interval.
4. Press START.
5. Observe telemetry cards, charts, anomaly flags, and alerts.
6. Press STOP to retain the data but stop new samples.
7. Press RESET to clear the simulated live-session records and simulated live alerts.

### Workflow B — Analyse historical and new CSV data

1. Prepare historical and/or new-reading CSV files.
2. Upload the historical file in the historical uploader.
3. Upload the new readings in the new-reading uploader.
4. Run **ANALYSE / IMPORT TELEMETRY**.
5. Review the baseline and astronaut condition summary.
6. Review anomaly rows and alert explanations.
7. Select the CSV source in Mission Control to inspect imported data independently.

### Workflow C — Replay imported readings

1. Import a new-reading CSV.
2. Select the CSV import data source.
3. Select the astronaut or crew view.
4. Prepare/reset the CSV replay.
5. Choose playback speed.
6. Play/resume and inspect the time-series charts.
7. Pause, stop, or reset the replay cursor as needed.

### Workflow D — Export analytics

1. Open Advanced Analytics.
2. Select an astronaut and reporting interval.
3. Inspect available summaries, comparisons, correlations, and trend estimates.
4. Export the PDF health report or selected telemetry CSV.

## 8. Data quality and analytical safeguards

The ingestion layer checks structural and value-level data quality. The current supported indicator/unit mapping is:

| Indicator | Unit |
|---|---|
| heart_rate | bpm |
| spo2 | percent |
| temperature | C |
| sleep_duration | hours |
| fatigue | score |

The system rejects unsupported indicator names, unit mismatches, invalid timestamps, missing required fields, configured out-of-range values, and duplicate astronaut/timestamp/indicator rows.

The application should continue to distinguish:
- missing data from normal data;
- provisional references from personal historical baselines;
- synthetic records from imported source records;
- statistical anomalies from medical diagnoses;
- descriptive trends from validated predictions.

## 9. Security, privacy, and deployment considerations

The current prototype does not implement authentication, role-based authorization, per-user database isolation, or production-grade audit controls. It should not be used to store identifiable or sensitive real health data in a public demo environment.

SQLite is suitable for local demonstration and limited single-instance use. Cloud deployment must account for ephemeral filesystems and process restarts. If historical persistence is required, use a managed persistent database and define backup, access-control, retention, and recovery policies.

A GitHub merge confirms that code reached the repository's `main` branch. It does not independently confirm that Streamlit Cloud completed deployment or that the deployed browser workflow passed manual testing.

## 10. Current limitations and risks

1. **Synthetic telemetry:** the built-in source is simulated and not connected to spacecraft hardware.
2. **No NASA dataset review yet:** no NASA file or official NASA requirements document was attached for this report.
3. **No blood pressure fields:** the current schema and supported CSV mapping do not include systolic or diastolic blood pressure.
4. **No clinical validation:** baseline definitions, thresholds, anomaly logic, and alert patterns are not clinically validated.
5. **No validated prediction:** trend extrapolation is a simple statistical demonstration.
6. **No production security:** authentication and per-user access isolation are not implemented.
7. **Deployment persistence:** local SQLite files may not survive cloud restarts if the host filesystem is ephemeral.
8. **Manual deployment verification:** each important UI change must be checked in the deployed application; a successful merge alone is insufficient.

## 11. Development process and quality control

The intended development workflow is one focused change per branch and pull request:

1. synchronize local `main`;
2. create a branch named for the task;
3. change only the relevant files;
4. inspect `git diff` and `git status`;
5. run targeted tests and the full test suite where practical;
6. push the branch and open a PR;
7. review changed files, mergeability, and available checks;
8. merge only when there are no unresolved conflicts or blocking checks;
9. verify the Streamlit deployment and manually exercise the affected UI path;
10. record any unverified step honestly.

Automated test status, merge status, cloud deployment status, and manual browser verification are separate facts and should never be conflated.

## 12. Next engineering steps

### Priority 1 — Review the actual NASA source material

Before changing the data model, obtain and inspect the NASA source files and any accompanying documentation. Record:
- dataset identity, provenance, and license;
- intended research/operational context;
- schema and units;
- time resolution and timestamp meaning;
- participant/subject identifier structure;
- missingness and quality flags;
- whether the data are physiological, environmental, exercise, sleep, or other measurements.

Do not map fields based only on similar names. Confirm their definitions and units.

### Priority 2 — Build a traceable data mapping

Create a field-mapping specification from the NASA source schema to ASTRAWELL's canonical schema. Keep unsupported source fields documented rather than silently discarding or mislabelling them. Add new indicators only after the source definitions and units are understood.

### Priority 3 — Validate with source-grounded test cases

Create tests for:
- valid source records;
- missing values;
- unit conversions (only when documented);
- timestamp parsing;
- duplicate handling;
- outlier and quality flags;
- baseline calculations;
- replay ordering;
- dashboard source filtering.

### Priority 4 — Improve reproducibility and deployment

Record dataset versions, import metadata, transformation parameters, and analysis configuration. Use persistent storage and explicit access controls before handling sensitive data.

## 13. Conclusion

ASTRAWELL currently demonstrates a complete prototype workflow for synthetic and CSV-based astronaut-style telemetry: ingestion, validation, storage, baseline-relative screening, alert explanation, visualization, replay, and reporting.

The next meaningful step is not to label the current prototype as NASA-integrated. It is to inspect the actual NASA source material, document its provenance and schema, and build a defensible mapping and validation process before integrating it. That work will determine which indicators, baselines, and analyses are technically justified.

---

**Document status:** Current implementation report; NASA-source review pending.  
**Intended use:** Project documentation and technical handoff, not clinical or mission-operational guidance.
