
import streamlit as st
import pandas as pd
import plotly.express as px

from analytics.baseline import calculate_baseline
from analytics.anomaly_detector import detect_anomalies
from analytics.rule_engine import evaluate_health_patterns

from preprocessing.validator import validate_health_data
from preprocessing.normalizer import normalize_health_data

from decision_support.alert_generator import generate_alerts
from decision_support.explanations import explain_alert

from database.db import (
    initialize_database,
    save_health_readings,
    save_baselines,
    save_alerts,
    get_alert_history
)

# ---------------- CONFIG ----------------

st.set_page_config(
    page_title="ASTRAWELL | Mission Control",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------- CUSTOM DESIGN ----------------

st.markdown("""
<style>
.stApp {
    background: #07111f;
    color: #e5edf7;
}

[data-testid="stSidebar"] {
    background: #0b192a;
    border-right: 1px solid #1c344c;
}

h1, h2, h3 {
    color: #e7f4ff !important;
}

p, label {
    color: #a9bdd1;
}

[data-testid="stMetric"] {
    background: linear-gradient(135deg, #10243a, #0c1b2c);
    border: 1px solid #1d405b;
    padding: 18px;
    border-radius: 12px;
}

[data-testid="stMetricValue"] {
    color: #45d9ef;
}

div.stButton > button {
    background: #087e9b;
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    width: 100%;
}

div.stButton > button:hover {
    background: #09a4c5;
    color: white;
}

hr {
    border-color: #1d3449;
}

.hero {
    background: linear-gradient(110deg, #102943, #0a1728);
    border: 1px solid #1e4963;
    border-radius: 15px;
    padding: 24px;
    margin-bottom: 20px;
}

.hero-title {
    color: #48d9ed;
    font-size: 30px;
    font-weight: 800;
    letter-spacing: 2px;
}

.hero-sub {
    color: #a9c2d7;
    font-size: 13px;
    letter-spacing: 1px;
}

.status {
    color: #42dba2;
    font-weight: bold;
}

.section-label {
    color: #4bd5e9;
    font-size: 12px;
    font-weight: bold;
    letter-spacing: 2px;
    margin-top: 18px;
}

</style>
""", unsafe_allow_html=True)


# ---------------- INITIALIZATION ----------------

initialize_database()

st.markdown("""
<div class="hero">
    <div class="hero-title">ASTRAWELL</div>
    <div class="hero-sub">
        AUTONOMOUS ASTRONAUT HEALTH INTELLIGENCE SYSTEM
    </div>
    <br>
    <span class="status">● LOCAL SYSTEM READY</span>
    &nbsp;&nbsp; | &nbsp;&nbsp;
    OFFLINE-FIRST MONITORING
</div>
""", unsafe_allow_html=True)


# ---------------- SIDEBAR ----------------

st.sidebar.markdown("## 🚀 MISSION CONTROL")
st.sidebar.caption("ASTRAWELL HEALTH INTELLIGENCE")

page = st.sidebar.radio(
    "NAVIGATION",
    [
        "Mission Overview",
        "Health Analytics",
        "Alert Centre",
        "System Information"
    ]
)

st.sidebar.divider()

st.sidebar.markdown("### DATA INPUT")

historical_file = st.sidebar.file_uploader(
    "Historical baseline CSV",
    type=["csv"],
    key="historical"
)

new_file = st.sidebar.file_uploader(
    "New health readings CSV",
    type=["csv"],
    key="new_readings"
)

st.sidebar.caption(
    "Historical data establishes the baseline. "
    "New readings are compared against it."
)


# ---------------- ANALYSIS ----------------

if historical_file is not None:

    if st.sidebar.button("ANALYSE HEALTH DATA"):

        try:
            historical_raw = pd.read_csv(historical_file)

            historical_validation = validate_health_data(
                historical_raw
            )

            if not historical_validation["valid"]:
                st.error("Historical dataset validation failed.")

                for error in historical_validation["errors"]:
                    st.write("•", error)

                st.stop()

            historical = normalize_health_data(
                historical_raw
            )

            baseline = calculate_baseline(historical)

            if new_file is not None:

                new_raw = pd.read_csv(new_file)

                new_validation = validate_health_data(new_raw)

                if not new_validation["valid"]:
                    st.error("New readings validation failed.")

                    for error in new_validation["errors"]:
                        st.write("•", error)

                    st.stop()

                new_readings = normalize_health_data(
                    new_raw
                )

                if not set(new_readings["astronaut_id"]).issubset(
                    set(baseline["astronaut_id"])
                ):
                    st.error(
                        "New readings contain an astronaut "
                        "without a historical baseline."
                    )
                    st.stop()

                anomalies = detect_anomalies(
                    new_readings,
                    baseline
                )

                rules = evaluate_health_patterns(
                    anomalies
                )

                alerts = generate_alerts(
                    rules,
                    anomalies
                )

                explanations = [
                    explain_alert(alert)
                    for alert in alerts
                ]

            else:
                new_readings = historical.copy()
                anomalies = pd.DataFrame()
                alerts = []
                explanations = []

            st.session_state["analysis"] = {
                "historical": historical,
                "baseline": baseline,
                "readings": new_readings,
                "anomalies": anomalies,
                "alerts": alerts,
                "explanations": explanations
            }

            # Persist results locally
            save_health_readings(historical)
            save_baselines(baseline)

            if new_file is not None:
                save_alerts(alerts)

            st.sidebar.success("Analysis completed.")

        except Exception as error:
            st.error(f"Analysis failed: {error}")


# ---------------- LOAD RESULTS ----------------

result = st.session_state.get("analysis")


# ---------------- MISSION OVERVIEW ----------------

if page == "Mission Overview":

    st.markdown("## MISSION HEALTH OVERVIEW")

    if result is None:

        st.info(
            "Upload historical health data and select "
            "ANALYSE HEALTH DATA to begin."
        )

    else:

        readings = result["readings"]
        baseline = result["baseline"]
        anomalies = result["anomalies"]
        alerts = result["alerts"]

        astronauts = readings["astronaut_id"].unique()

        st.caption(
            f"MONITORED CREW PROFILE: {', '.join(astronauts)}"
        )

        latest = (
            readings.sort_values("timestamp")
            .groupby(["astronaut_id", "indicator"])
            .tail(1)
            .set_index("indicator")
        )

        # Health metrics
        indicators = [
            ("heart_rate", "HEART RATE", "BPM"),
            ("spo2", "OXYGEN SATURATION", "%"),
            ("temperature", "BODY TEMPERATURE", "°C"),
            ("sleep_duration", "SLEEP", "HRS"),
            ("fatigue", "FATIGUE", "/5")
        ]

        cols = st.columns(5)

        for col, (key, label, unit) in zip(cols, indicators):

            if key in latest.index:
                value = latest.loc[key, "value"]
                col.metric(label, f"{value} {unit}")
            else:
                col.metric(label, "NO DATA")

        st.divider()

        left, right = st.columns([2, 1])

        with left:

            st.markdown("### HEALTH TELEMETRY")

            selected = st.selectbox(
                "Select health indicator",
                readings["indicator"].unique()
            )

            chart_data = readings[
                readings["indicator"] == selected
            ].sort_values("timestamp")

            fig = px.line(
                chart_data,
                x="timestamp",
                y="value",
                markers=True,
                template="plotly_dark",
                title=f"{selected.upper()} HISTORY"
            )

            fig.update_layout(
                paper_bgcolor="#0b192a",
                plot_bgcolor="#0b192a",
                font_color="#dceaf5"
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

        with right:

            st.markdown("### SYSTEM SUMMARY")

            st.metric(
                "TOTAL READINGS",
                len(readings)
            )

            st.metric(
                "ANOMALIES",
                int(anomalies["anomaly"].sum())
                if not anomalies.empty else 0
            )

            st.metric(
                "GENERATED ALERTS",
                len(alerts)
            )

            if new_file is None:
                st.info(
                    "Baseline preview only. Upload new readings "
                    "to perform monitoring."
                )
            elif alerts:
                st.warning("Attention: alerts generated.")
            else:
                st.success("No configured anomaly rules triggered.")


# ---------------- HEALTH ANALYTICS ----------------

elif page == "Health Analytics":

    st.markdown("## PERSONAL HEALTH ANALYTICS")

    if result is None:
        st.info("Analyse a dataset first.")

    else:

        st.markdown("### PERSONAL BASELINE")

        st.dataframe(
            result["baseline"],
            use_container_width=True,
            hide_index=True
        )

        st.markdown("### READING COMPARISON")

        if not result["anomalies"].empty:

            st.dataframe(
                result["anomalies"],
                use_container_width=True,
                hide_index=True
            )

        else:
            st.info("No new readings have been analysed yet.")


# ---------------- ALERT CENTRE ----------------

elif page == "Alert Centre":

    st.markdown("## MISSION ALERT CENTRE")

    if result is not None and result["alerts"]:

        for explanation in result["explanations"]:

            with st.expander(
                f"{explanation['priority'].upper()} | "
                f"{explanation['alert_id']}"
            ):

                st.write(explanation["summary"])

                for detail in explanation["details"]:

                    st.write(
                        f"**{detail['indicator']}**"
                    )

                    st.write(
                        f"Current: {detail['current_value']} | "
                        f"Baseline: {detail['baseline_value']}"
                    )

                st.info(
                    explanation["recommended_action"]
                )

    else:
        st.success("No active alerts in the current analysis.")

    st.divider()

    st.markdown("### STORED ALERT HISTORY")

    history = get_alert_history()

    if history:
        st.dataframe(
            pd.DataFrame(history),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.caption("No stored alert history.")


# ---------------- SYSTEM INFORMATION ----------------

elif page == "System Information":

    st.markdown("## SYSTEM INFORMATION")

    st.markdown("""
    **ASTRAWELL architecture**

    - Python-based processing engine
    - Pandas health-data processing
    - Statistical personal baselines
    - Rule-based anomaly detection
    - Explainable decision support
    - SQLite local database
    - Streamlit user interface

    **Supported health indicators**

    - Heart rate
    - SpO₂
    - Body temperature
    - Sleep duration
    - Self-reported fatigue

    **Operational design**

    Offline-first local data processing.
    No continuous cloud connection is required.
    """)

    st.caption(
        "Research prototype. Not a validated medical device."
    )
