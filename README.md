# Arlog

Arlo feed event archiver. Polls the Arlo web app feed on a configurable interval and stores all events in a local SQLite database for long-term retention.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Configuration

Create a `.env` file or set environment variables:

| Variable | Default | Description |
|---|---|---|
| `ARLOG_ARLO_EMAIL` | *(required)* | Arlo account email |
| `ARLOG_ARLO_PASSWORD` | *(required)* | Arlo account password |
| `ARLOG_POLL_INTERVAL` | `300` | Seconds between poll cycles |
| `ARLOG_DB_PATH` | `./arlog.db` | Path to SQLite database |
| `ARLOG_HEADLESS` | `true` | Run browser headless (`true`/`false`) |
| `ARLOG_BROWSER_STATE_DIR` | `~/.arlog/browser_state` | Browser session/profile storage |

## Usage

```bash
python arlog.py
```

Arlog will continuously poll the Arlo feed and store events in the SQLite database. Press `Ctrl+C` to shut down gracefully.

If your account requires 2FA, run with `ARLOG_HEADLESS=false` first to complete the 2FA prompt in the browser, then restart in headless mode.

## Database

Arlog creates two tables:

- **`events`** -- scraped feed events with device name, event type, timestamp, and raw JSON
- **`poll_log`** -- history of each poll cycle (timestamp, event counts, success/error status)
