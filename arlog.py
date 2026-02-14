#!/usr/bin/env python3
"""Arlog: Arlo feed event archiver.

Polls the Arlo web app feed on a configurable interval and stores
all events in a local SQLite database for long-term retention.
"""

import logging
import signal
import sys
import time

import config
import db
import scraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("arlog")

_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    log.info(f"Received signal {signum}, shutting down...")
    _shutdown = True


def poll_once(conn):
    """Run a single poll cycle: scrape feed and insert new events."""
    try:
        events = scraper.scrape_feed()
        if events:
            inserted = db.insert_events(conn, events)
            log.info(f"Poll complete: {inserted} new events (of {len(events)} total)")
        else:
            inserted = 0
            log.info("Poll complete: no events returned")
        db.log_poll(conn, events_total=len(events), events_new=inserted)
    except Exception as exc:
        log.exception("Error during poll cycle")
        db.log_poll(conn, events_total=0, events_new=0, success=False, error=str(exc))


def main():
    global _shutdown

    log.info("Arlog starting up")
    log.info(f"  Poll interval: {config.POLL_INTERVAL}s")
    log.info(f"  Database: {config.DB_PATH}")
    log.info(f"  Headless: {config.HEADLESS}")

    if not config.ARLO_EMAIL or not config.ARLO_PASSWORD:
        log.error("Set ARLOG_ARLO_EMAIL and ARLOG_ARLO_PASSWORD in .env or environment")
        sys.exit(1)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    conn = db.init_db(config.DB_PATH)

    try:
        while not _shutdown:
            poll_once(conn)
            # Sleep in short increments so we can respond to signals
            for _ in range(config.POLL_INTERVAL):
                if _shutdown:
                    break
                time.sleep(1)
    finally:
        conn.close()
        log.info("Arlog shut down")


if __name__ == "__main__":
    main()
