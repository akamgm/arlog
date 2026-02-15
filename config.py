import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ARLO_EMAIL = os.environ.get("ARLOG_ARLO_EMAIL", "")
ARLO_PASSWORD = os.environ.get("ARLOG_ARLO_PASSWORD", "")

POLL_INTERVAL = int(os.environ.get("ARLOG_POLL_INTERVAL", "300"))
DB_PATH = os.environ.get("ARLOG_DB_PATH", "./arlog.db")
HEADLESS = os.environ.get("ARLOG_HEADLESS", "true").lower() in ("true", "1", "yes")

BROWSER_STATE_DIR = Path(
    os.environ.get(
        "ARLOG_BROWSER_STATE_DIR",
        Path.home() / ".arlog" / "browser_state",
    )
)

NTFY_TOPIC = os.environ.get("ARLOG_NTFY_TOPIC", "")
