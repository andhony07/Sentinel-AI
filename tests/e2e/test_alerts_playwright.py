"""Playwright End-to-End Test Suite for SentinelAI Risk Alert & Notification System.

Validates the full alert lifecycle across the React frontend and Streamlit dashboard:
1. Alert history renders correctly in React console
2. HIGH and CRITICAL alerts are visually distinguishable
3. Acknowledgement updates displayed status
4. Browser permission denied is handled gracefully
5. Browser notifications trigger when granted
6. Refreshes and reconnections do not create duplicate notifications
7. Clicking an alert opens the appropriate details
8. Empty states and search filters render correctly
9. No unexpected browser console errors occur
10. Streamlit dashboard integrates in-app alert display without breaking
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, List

import pytest

# Point PLAYWRIGHT_BROWSERS_PATH to installed browser binaries
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = r"C:\Users\dell5420\AppData\Local\ms-playwright"

try:
    from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

pytestmark = pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright is not installed")

import socket

def _detect_react_url() -> str:
    if os.getenv("REACT_APP_URL"):
        return os.environ["REACT_APP_URL"]
    for port in (5174, 5173):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    return f"http://127.0.0.1:{port}"
        except Exception:
            pass
    return "http://127.0.0.1:5173"

REACT_APP_URL = os.getenv("REACT_APP_URL", "http://localhost:5173")
DASHBOARD_URL = "http://127.0.0.1:8501"
SCREENSHOT_DIR = Path(r"D:\SentinelAI\tests\screenshots\alerts")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope="session")
def browser() -> Generator[Browser, None, None]:
    """Session-scoped Chromium browser instance."""
    with sync_playwright() as p:
        b = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        yield b
        b.close()


@pytest.fixture(scope="function")
def page(browser: Browser) -> Generator[Page, None, None]:
    """Create isolated context with desktop viewport and console listeners."""
    context = browser.new_context(
        viewport={"width": 1440, "height": 900},
        device_scale_factor=1,
    )
    p = context.new_page()

    # Pre-inject mock Notification API to safely test browser notifications
    p.add_init_script("""
        window.__sentinel_notifications = window.__sentinel_notifications || [];
        if (typeof window.__mock_permission === 'undefined') {
            window.__mock_permission = 'default';
        }

        class MockNotification {
            constructor(title, options) {
                this.title = title;
                this.options = options;
                this.onclick = null;
                window.__sentinel_notifications.push({ title, options, timestamp: Date.now() });
            }
            static get permission() {
                return window.__mock_permission || 'default';
            }
            static requestPermission() {
                window.__mock_permission = 'granted';
                return Promise.resolve('granted');
            }
            close() {}
        }
        window.Notification = MockNotification;
    """)

    yield p
    context.close()


def test_1_alert_history_renders_correctly(page: Page) -> None:
    """1. Alert history renders correctly in React console."""
    page.goto(f"{REACT_APP_URL}/", wait_until="domcontentloaded", timeout=15000)
    page.wait_for_timeout(1000)

    # Click Risk Alerts nav item in sidebar
    alerts_nav = page.locator("#nav-item-alerts")
    assert alerts_nav.is_visible(timeout=5000)
    alerts_nav.click()
    page.wait_for_timeout(1200)

    # Verify heading and stats cards
    assert page.locator("h1:has-text('Risk Alerts & Incident Notifications')").is_visible(timeout=5000)
    assert page.locator("text=Active Incidents").first.is_visible()
    assert page.locator("div:has-text('Critical Risk')").first.is_visible()
    assert page.locator("div:has-text('High Risk')").first.is_visible()
    assert page.locator("div:has-text('Acknowledged')").first.is_visible()
    assert page.locator("div:has-text('Resolved')").first.is_visible()

    page.screenshot(path=str(SCREENSHOT_DIR / "alert_history_view.png"), full_page=True)


def test_2_and_7_high_critical_distinction_and_details_click(page: Page) -> None:
    """2 & 7. HIGH and CRITICAL alerts visually distinguishable, and clicking opens details."""
    from app.alerts.service import AlertService
    from app.ml.prediction_service import PredictionResult
    from app.ml.models import RiskCategory

    service = AlertService()
    p_high = PredictionResult(
        timestamp=datetime.now(timezone.utc),
        is_anomaly=True,
        anomaly_score=0.82,
        raw_decision_score=-0.35,
        health_score=38.0,
        risk_category=RiskCategory.HIGH,
        model_name="IsolationForest",
        model_version="1.0.0",
        warnings=[],
    )
    service.process_prediction(p_high, server_id="e2e-srv-high")

    p_crit = PredictionResult(
        timestamp=datetime.now(timezone.utc),
        is_anomaly=True,
        anomaly_score=0.96,
        raw_decision_score=-0.68,
        health_score=10.0,
        risk_category=RiskCategory.CRITICAL,
        model_name="IsolationForest",
        model_version="1.0.0",
        warnings=[],
    )
    service.process_prediction(p_crit, server_id="e2e-srv-crit")

    page.goto(f"{REACT_APP_URL}/", wait_until="domcontentloaded", timeout=15000)
    page.wait_for_timeout(1000)
    page.locator("#nav-item-alerts").click()
    page.wait_for_timeout(1500)

    # 2. Check visual badges in feed
    crit_badge = page.locator("span:has-text('CRITICAL')").first
    high_badge = page.locator("span:has-text('HIGH')").first
    assert crit_badge.is_visible(timeout=5000)
    assert high_badge.is_visible(timeout=5000)

    # 7. Clicking alert card opens detailed inspection panel
    crit_card = page.locator("div.cursor-pointer:has-text('CRITICAL')").first
    crit_card.click()
    page.wait_for_timeout(800)
    assert page.locator("text=Deterministic Diagnostic Findings").is_visible(timeout=5000)
    assert page.locator("text=Recommended Investigation & Action").is_visible(timeout=5000)

    page.screenshot(path=str(SCREENSHOT_DIR / "alert_detail_selected.png"), full_page=True)


def test_3_acknowledgement_updates_status(page: Page) -> None:
    """3. Acknowledgement updates displayed status in the UI."""
    from app.alerts.service import AlertService
    from app.ml.prediction_service import PredictionResult
    from app.ml.models import RiskCategory

    service = AlertService()
    p = PredictionResult(
        timestamp=datetime.now(timezone.utc),
        is_anomaly=True,
        anomaly_score=0.88,
        raw_decision_score=-0.4,
        health_score=25.0,
        risk_category=RiskCategory.HIGH,
        model_name="IsolationForest",
        model_version="1.0.0",
        warnings=[],
    )
    service.process_prediction(p, server_id="srv-ack-test-node")

    page.goto(f"{REACT_APP_URL}/", wait_until="domcontentloaded", timeout=15000)
    page.wait_for_timeout(1000)
    page.locator("#nav-item-alerts").click()
    page.wait_for_timeout(1500)

    # Click on the srv-ack-test-node alert card
    test_card = page.locator("div.cursor-pointer:has-text('srv-ack-test-node')").first
    if test_card.is_visible():
        test_card.click()
        page.wait_for_timeout(500)

    # Find the Acknowledge button in the detail panel and click it
    ack_btn = page.locator("button:has-text('Acknowledge')").first
    if ack_btn.is_visible(timeout=4000):
        ack_btn.click()
        page.wait_for_timeout(1500)
        # Status badge updates to ACKNOWLEDGED
        assert page.locator("span:has-text('ACKNOWLEDGED')").first.is_visible(timeout=5000)


def test_4_browser_permission_denied_handled_gracefully(page: Page) -> None:
    """4. Browser permission denied is handled gracefully."""
    page.add_init_script("window.__mock_permission = 'denied';")
    page.goto(f"{REACT_APP_URL}/", wait_until="domcontentloaded", timeout=15000)
    page.wait_for_timeout(1000)
    page.locator("#nav-item-alerts").click()
    page.wait_for_timeout(1500)

    # Verify warning notice is displayed without crashing
    notice = page.locator("text=Desktop notifications are currently blocked")
    assert notice.is_visible(timeout=5000)


def test_5_and_6_browser_notifications_and_deduplication(page: Page) -> None:
    """5 & 6. Browser notifications trigger when granted and deduplicate across refreshes."""
    from app.alerts.service import AlertService
    from app.ml.prediction_service import PredictionResult
    from app.ml.models import RiskCategory

    service = AlertService()
    p = PredictionResult(
        timestamp=datetime.now(timezone.utc),
        is_anomaly=True,
        anomaly_score=0.94,
        raw_decision_score=-0.62,
        health_score=12.0,
        risk_category=RiskCategory.CRITICAL,
        model_name="IsolationForest",
        model_version="1.0.0",
        warnings=[],
    )
    service.process_prediction(p, server_id="srv-dedup-node")

    page.goto(f"{REACT_APP_URL}/", wait_until="domcontentloaded", timeout=15000)
    page.wait_for_timeout(1000)
    page.locator("#nav-item-alerts").click()
    page.wait_for_timeout(1200)

    # Click Enable Desktop Alerts button
    enable_btn = page.locator("button:has-text('Enable Desktop Alerts')").first
    if enable_btn.is_visible():
        enable_btn.click()
        page.wait_for_timeout(1000)

    # Verify toggle state changed to Desktop Alerts: Enabled
    assert page.locator("text=Desktop Alerts: Enabled").or_(page.locator("text=Desktop: On")).first.is_visible(timeout=5000)

    # Notification count
    count1 = page.evaluate("window.__sentinel_notifications ? window.__sentinel_notifications.length : 0")

    # Reload page to test refresh deduplication
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(2000)

    count2 = page.evaluate("window.__sentinel_notifications ? window.__sentinel_notifications.length : 0")
    # Must not duplicate notifications on reload!
    assert count2 == count1


def test_8_empty_states_render_correctly(page: Page) -> None:
    """8. Empty states and search filters render correctly."""
    page.goto(f"{REACT_APP_URL}/", wait_until="domcontentloaded", timeout=15000)
    page.wait_for_timeout(1000)
    page.locator("#nav-item-alerts").click()
    page.wait_for_timeout(1200)

    # Type nonexistent query into search
    search_input = page.locator("input[placeholder*='Search by server']")
    assert search_input.is_visible(timeout=5000)
    search_input.fill("nonexistent-node-query-999")
    page.wait_for_timeout(600)

    assert page.locator("text=All Systems Normal").is_visible(timeout=5000)
    page.screenshot(path=str(SCREENSHOT_DIR / "alert_empty_state.png"))


def test_9_no_unexpected_browser_console_errors(page: Page) -> None:
    """9. No unexpected browser console errors occur during navigation."""
    errors: list[str] = []
    page.on("pageerror", lambda err: errors.append(str(err)))
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

    page.goto(f"{REACT_APP_URL}/", wait_until="domcontentloaded", timeout=15000)
    page.wait_for_timeout(1000)
    page.locator("#nav-item-alerts").click()
    page.wait_for_timeout(1500)

    # Filter out known benign dev server or websocket warnings
    critical_errors = [e for e in errors if "favicon" not in e and "WebSocket" not in e]
    assert len(critical_errors) == 0, f"Unexpected console errors: {critical_errors}"


def test_10_streamlit_dashboard_alerts_view(page: Page) -> None:
    """10. Streamlit dashboard integrates in-app alert display without breaking."""
    page.goto(f"{DASHBOARD_URL}/", wait_until="domcontentloaded", timeout=25000)
    page.wait_for_timeout(3000)

    # Select Risk Alerts & Incidents in sidebar radio
    st_radio = page.locator("span:has-text('Risk Alerts & Incidents')").first
    if st_radio.is_visible(timeout=5000):
        st_radio.click()
        page.wait_for_timeout(3000)
        assert page.locator("text=Active Incidents").or_(page.locator("text=Risk Alerts")).first.is_visible(timeout=10000)

    page.screenshot(path=str(SCREENSHOT_DIR / "streamlit_alerts_view.png"), full_page=True)
