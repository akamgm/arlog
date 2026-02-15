"""Push notifications via ntfy.sh."""

import logging
import urllib.request

import config

log = logging.getLogger("arlog.notify")

NTFY_URL = "https://ntfy.sh"


def send(events: list[dict]) -> bool:
    """Send a single summary notification for new events. Returns True if sent."""
    if not config.NTFY_TOPIC or not events:
        return False

    lines = []
    for event in events:
        device = event.get("device_name") or "Unknown device"
        event_type = event.get("event_type") or "event"
        description = event.get("description") or ""
        line = f"{device}: {event_type}"
        if description:
            line += f" — {description}"
        lines.append(line)

    count = len(events)
    title = f"Arlo: {count} new event{'s' if count != 1 else ''}"
    body = "\n".join(lines)

    try:
        req = urllib.request.Request(
            f"{NTFY_URL}/{config.NTFY_TOPIC}",
            data=body.encode(),
            headers={"Title": title},
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception:
        log.exception("Failed to send notification")
        return False
