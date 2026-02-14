import hashlib
import json
import logging
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, sync_playwright
from playwright.sync_api import TimeoutError as PwTimeout

import config

log = logging.getLogger(__name__)

ARLO_BASE = "https://my.arlo.com"
ARLO_FEED_URL = f"{ARLO_BASE}/#/feed"
ARLO_LOGIN_URL = f"{ARLO_BASE}/#/login"


def _ensure_state_dir() -> Path:
    path = Path(config.BROWSER_STATE_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _make_event_id(event: dict) -> str:
    """Generate a stable unique ID for an event from its raw data."""
    # Prefer Arlo's own ID if present
    for key in ("id", "eventId", "arloid", "transId"):
        if key in event:
            return str(event[key])
    # Fallback: hash the whole event
    blob = json.dumps(event, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:32]


def _parse_event(raw: dict) -> dict:
    """Normalize a raw feed event into our storage format."""
    device = (
        raw.get("deviceName") or raw.get("deviceId") or raw.get("from") or "unknown"
    )
    event_type = (
        raw.get("type")
        or raw.get("action")
        or raw.get("properties", {}).get("type")
        or raw.get("eventType")
        or "unknown"
    )
    timestamp = (
        raw.get("createdDate")
        or raw.get("utcCreatedDate")
        or raw.get("timestamp")
        or raw.get("localCreatedDate")
        or ""
    )
    description = raw.get("description") or raw.get("reason") or ""

    return {
        "arlo_event_id": _make_event_id(raw),
        "device_name": device,
        "event_type": event_type,
        "timestamp": str(timestamp),
        "description": description,
        "raw": raw,
    }


def _is_feed_api_response(url: str) -> bool:
    """Check if a URL looks like an Arlo feed/events API call."""
    feed_patterns = [
        "/hmsweb/users/library",
        "/hmsweb/users/devices/automation/active",
        "/hmsweb/timeline",
        "/feed",
        "/events",
        "/history",
        "/notifications",
    ]
    return any(p in url for p in feed_patterns)


def _login(page: Page) -> bool:
    """Perform Arlo login. Returns True if login succeeded."""
    log.info("Navigating to Arlo login...")
    page.goto(ARLO_LOGIN_URL, wait_until="networkidle", timeout=60000)

    # Check if already logged in (redirected past login)
    if "#/login" not in page.url and "#/feed" in page.url:
        log.info("Already logged in via saved session")
        return True

    if not config.ARLO_EMAIL or not config.ARLO_PASSWORD:
        log.error("ARLOG_ARLO_EMAIL and ARLOG_ARLO_PASSWORD must be set")
        return False

    log.info("Filling login form...")
    # Wait for email field and fill
    page.wait_for_selector('input[type="email"]', timeout=30000)
    page.fill('input[type="email"]', config.ARLO_EMAIL)
    page.click('button[type="submit"], a[data-qa="login-submit"]')

    # Wait for password field
    page.wait_for_selector('input[type="password"]', timeout=30000)
    page.fill('input[type="password"]', config.ARLO_PASSWORD)
    page.click('button[type="submit"], a[data-qa="login-submit"]')

    # Wait for either 2FA prompt or successful redirect to feed
    log.info("Waiting for 2FA or feed redirect...")
    try:
        page.wait_for_url("**/feed**", timeout=120000)
        log.info("Login successful")
        return True
    except PwTimeout:
        # Might be on 2FA page — if headless, we can't proceed
        if config.HEADLESS:
            log.error(
                "Login appears to require 2FA. Run with ARLOG_HEADLESS=false "
                "to complete 2FA manually, then restart in headless mode."
            )
            return False
        # Non-headless: wait longer for user to complete 2FA
        log.info("Please complete 2FA in the browser window...")
        try:
            page.wait_for_url("**/feed**", timeout=300000)  # 5 min
            log.info("Login successful after 2FA")
            return True
        except PwTimeout:
            log.error("Login timed out waiting for 2FA")
            return False


def _scrape_feed_via_network(page: Page) -> list[dict]:
    """Navigate to feed and capture API responses via network interception."""
    captured_events = []

    def handle_response(response):
        try:
            if not _is_feed_api_response(response.url):
                return
            if response.status != 200:
                return
            content_type = response.headers.get("content-type", "")
            if "json" not in content_type and "javascript" not in content_type:
                return

            body = response.json()
            # Arlo API typically wraps data in {"data": [...], "success": true}
            events = []
            if isinstance(body, dict):
                if "data" in body and isinstance(body["data"], list):
                    events = body["data"]
                elif "data" in body and isinstance(body["data"], dict):
                    events = [body["data"]]
                elif isinstance(body.get("items"), list):
                    events = body["items"]
            elif isinstance(body, list):
                events = body

            for e in events:
                if isinstance(e, dict):
                    captured_events.append(e)
        except Exception:
            pass  # not JSON or other error, skip

    page.on("response", handle_response)

    log.info("Navigating to feed...")
    page.goto(ARLO_FEED_URL, wait_until="networkidle", timeout=60000)

    # Scroll down to trigger loading more events
    for _ in range(3):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(2000)

    page.remove_listener("response", handle_response)
    return captured_events


def _scrape_feed_via_dom(page: Page) -> list[dict]:
    """Fallback: scrape feed events from the DOM."""
    log.info("Attempting DOM-based feed scraping as fallback...")
    page.goto(ARLO_FEED_URL, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(5000)

    events = page.evaluate("""
        () => {
            const items = document.querySelectorAll(
                '[class*="feed-item"], [class*="event-item"], ' +
                '[class*="timeline-item"], [class*="activity-item"], ' +
                '[data-test*="feed"], [data-qa*="feed"]'
            );
            return Array.from(items).map((el, i) => ({
                id: el.getAttribute('data-id') || el.getAttribute('id') || `dom-${i}-${Date.now()}`,
                text: el.innerText,
                html: el.innerHTML.substring(0, 500),
            }));
        }
    """)

    parsed = []
    for item in events:
        lines = [l.strip() for l in item.get("text", "").split("\n") if l.strip()]
        parsed.append(
            {
                "arlo_event_id": item.get("id", ""),
                "device_name": lines[0] if lines else "unknown",
                "event_type": lines[1] if len(lines) > 1 else "unknown",
                "timestamp": lines[2] if len(lines) > 2 else "",
                "description": " | ".join(lines),
                "raw": item,
            }
        )
    return parsed


def scrape_feed() -> list[dict]:
    """Main entry point: scrape the Arlo feed and return parsed events."""
    state_dir = _ensure_state_dir()
    state_path = state_dir / "state.json"

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(state_dir / "chromium_profile"),
            headless=config.HEADLESS,
            viewport={"width": 1280, "height": 900},
        )
        page = context.pages[0] if context.pages else context.new_page()

        # Try navigating directly to feed (might work if session is saved)
        try:
            page.goto(ARLO_FEED_URL, wait_until="networkidle", timeout=30000)
        except PwTimeout:
            pass

        # If redirected to login, authenticate
        if "#/login" in page.url or "login" in page.url.lower():
            if not _login(page):
                context.close()
                return []

        # Scrape via network interception
        raw_events = _scrape_feed_via_network(page)

        if not raw_events:
            log.warning("No events from network interception, trying DOM fallback")
            parsed = _scrape_feed_via_dom(page)
        else:
            parsed = [_parse_event(e) for e in raw_events]

        log.info(f"Scraped {len(parsed)} events from Arlo feed")
        context.close()
        return parsed
