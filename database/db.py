
import sqlite3
from pathlib import Path


DB_PATH = Path("database/astrawell.db")


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    return connection


def initialize_database():

    with get_connection() as conn:

        conn.executescript("""
        CREATE TABLE IF NOT EXISTS astronauts (
            astronaut_id TEXT PRIMARY KEY,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS health_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            astronaut_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            indicator TEXT NOT NULL,
            value REAL,
            unit TEXT,
            source TEXT,
            FOREIGN KEY (astronaut_id)
                REFERENCES astronauts(astronaut_id)
        );

        CREATE TABLE IF NOT EXISTS baselines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            astronaut_id TEXT NOT NULL,
            indicator TEXT NOT NULL,
            mean REAL,
            std REAL,
            minimum REAL,
            maximum REAL,
            count INTEGER,
            FOREIGN KEY (astronaut_id)
                REFERENCES astronauts(astronaut_id)
        );

        CREATE TABLE IF NOT EXISTS alerts (
            alert_id TEXT PRIMARY KEY,
            astronaut_id TEXT NOT NULL,
            timestamp TEXT,
            priority TEXT,
            rule TEXT,
            explanation TEXT,
            acknowledged INTEGER DEFAULT 0,
            FOREIGN KEY (astronaut_id)
                REFERENCES astronauts(astronaut_id)
        );
        """)


def save_health_readings(df):

    with get_connection() as conn:

        for astronaut_id in df["astronaut_id"].unique():
            conn.execute(
                "INSERT OR IGNORE INTO astronauts (astronaut_id) VALUES (?)",
                (astronaut_id,)
            )

        records = df[
            [
                "astronaut_id",
                "timestamp",
                "indicator",
                "value",
                "unit",
                "source"
            ]
        ].copy()

        records["timestamp"] = records["timestamp"].astype(str)

        conn.executemany(
            """
            INSERT INTO health_readings
            (astronaut_id, timestamp, indicator, value, unit, source)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            records.itertuples(index=False, name=None)
        )


def save_baselines(df):

    with get_connection() as conn:

        for astronaut_id in df["astronaut_id"].unique():
            conn.execute(
                "INSERT OR IGNORE INTO astronauts (astronaut_id) VALUES (?)",
                (astronaut_id,)
            )

        conn.executemany(
            """
            INSERT INTO baselines
            (astronaut_id, indicator, mean, std, minimum, maximum, count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            df.itertuples(index=False, name=None)
        )


def save_alerts(alert_list):

    with get_connection() as conn:

        for alert in alert_list:

            conn.execute(
                "INSERT OR IGNORE INTO astronauts (astronaut_id) VALUES (?)",
                (alert["astronaut_id"],)
            )

            conn.execute(
                """
                INSERT OR REPLACE INTO alerts
                (alert_id, astronaut_id, timestamp, priority,
                 rule, explanation, acknowledged)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert["alert_id"],
                    alert["astronaut_id"],
                    alert["timestamp"],
                    alert["priority"],
                    alert["rule"],
                    alert["explanation"],
                    int(alert["acknowledged"])
                )
            )


def get_alert_history():

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM alerts ORDER BY timestamp DESC"
        ).fetchall()

        return [dict(row) for row in rows]
