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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS poll_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            polled_at TEXT NOT NULL DEFAULT (datetime('now')),
            events_total INTEGER NOT NULL DEFAULT 0,
            events_new INTEGER NOT NULL DEFAULT 0,
            success INTEGER NOT NULL DEFAULT 1,
            error TEXT
        )
    """)
    conn.commit()
    return conn


def insert_events(
    conn: sqlite3.Connection, events: list[dict]
) -> tuple[int, list[dict]]:
    """Insert events, skipping duplicates. Returns (count, list) of newly inserted events."""
    inserted = 0
    new_events = []
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
            new_events.append(event)
        except sqlite3.IntegrityError:
            pass  # duplicate, skip
    conn.commit()
    return inserted, new_events


def log_poll(
    conn: sqlite3.Connection,
    events_total: int,
    events_new: int,
    success: bool = True,
    error: str | None = None,
):
    """Record a poll cycle in the poll_log table."""
    conn.execute(
        "INSERT INTO poll_log (events_total, events_new, success, error) VALUES (?, ?, ?, ?)",
        (events_total, events_new, 1 if success else 0, error),
    )
    conn.commit()
