import json
import sqlite3


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arlo_event_id TEXT UNIQUE NOT NULL,
            device_name TEXT,
            event_type TEXT,
            timestamp TEXT,
            description TEXT,
            raw_json TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_events_device ON events(device_name)
    """)
    conn.commit()
    return conn


def insert_events(conn: sqlite3.Connection, events: list[dict]) -> int:
    """Insert events, skipping duplicates. Returns count of newly inserted events."""
    inserted = 0
    for event in events:
        try:
            conn.execute(
                """
                INSERT INTO events (arlo_event_id, device_name, event_type, timestamp, description, raw_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event["arlo_event_id"],
                    event.get("device_name"),
                    event.get("event_type"),
                    event.get("timestamp"),
                    event.get("description"),
                    json.dumps(event.get("raw", {})),
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            pass  # duplicate, skip
    conn.commit()
    return inserted
