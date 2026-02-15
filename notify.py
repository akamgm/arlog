"""Push notifications via ntfy.sh."""

import logging
import urllib.request

import config

log = logging.getLogger("arlog.notify")

NTFY_URL = "https://ntfy.sh"


def send(events: list[dict]) -> int:
    """Send a notification for each event. Returns count of notifications sent."""
    if not config.NTFY_TOPIC:
        return 0

    sent = 0
    for event in events:
        device = event.get("device_name") or "Unknown device"
        event_type = event.get("event_type") or "event"
        description = event.get("description") or ""
        timestamp = event.get("timestamp") or ""

        title = f"Arlo: {device}"
        body = event_type
        if description:
            body += f" — {description}"
        if timestamp:
            body += f"\n{timestamp}"

        try:
            req = urllib.request.Request(
                f"{NTFY_URL}/{config.NTFY_TOPIC}",
                data=body.encode(),
                headers={"Title": title},
            )
            urllib.request.urlopen(req, timeout=10)
            sent += 1
        except Exception:
            log.exception(
                f"Failed to send notification for event {event.get('arlo_event_id')}"
            )

    return sent
