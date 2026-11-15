"""PDF report builder for ASTRAWELL descriptive analytics."""
from __future__ import annotations

from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def build_health_report(astronaut_id, readings, summary, comparisons, generated_at):
    """Build a compact PDF from already-computed dataframes."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=34, leftMargin=34, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("ASTRAWELL — Astronaut Health Intelligence Report", styles["Title"]),
        Paragraph(f"Astronaut: {astronaut_id} | Generated: {generated_at} UTC", styles["Normal"]),
        Spacer(1, 10),
        Paragraph("Research prototype. This report is not a diagnosis, medical recommendation, or validated clinical forecast. Review measurements using approved medical procedures.", styles["Italic"]),
        Spacer(1, 12),
        Paragraph("Telemetry summary", styles["Heading2"]),
    ]

    def add_table(df, columns, max_rows=18):
        if df is None or df.empty:
            story.append(Paragraph("No data available for this section.", styles["Normal"]))
            return
        subset = df.loc[:, [c for c in columns if c in df.columns]].head(max_rows).copy()
        values = [list(subset.columns)] + subset.fillna("—").astype(str).values.tolist()
        table = Table(values, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#12304A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B7C7D6")),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EEF4F8")]),
        ]))
        story.extend([table, Spacer(1, 10)])

    add_table(readings, ["ts", "heart_rate", "spo2", "temperature", "sleep_duration", "fatigue"], 20)
    story.append(Paragraph("Daily summary (most recent periods)", styles["Heading2"]))
    add_table(summary, ["period", "heart_rate_mean", "spo2_mean", "temperature_mean", "sleep_duration_mean", "fatigue_mean"], 14)
    story.append(Paragraph("Crew comparison (personal-baseline deviation)", styles["Heading2"]))
    add_table(comparisons, ["astronaut_id", "largest_baseline_deviation"], 12)
    doc.build(story)
    return buffer.getvalue()
