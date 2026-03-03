"""End-to-end Playwright test: full user journey with edge-case validation.

A single ordered test flow that walks through every major feature while also
verifying that invalid operations are properly rejected.  Recorded as an MP4
video in docs/videos/ at 1920x1080 so reviewers can watch the entire session.

Run with:
    uv run --with pytest,playwright,httpx pytest tests/test_playwright.py -v
"""

import glob as globmod
import multiprocessing
import os
import shutil
import subprocess
import time

import pytest

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "test_e2e.db")
BASE_URL = "http://127.0.0.1:8877"
VIDEO_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "videos")

TEST_EMAIL = "e2e-user@example.com"
TEST_PASSWORD = "StrongPass1!"


# ---------------------------------------------------------------------------
# Server management
# ---------------------------------------------------------------------------

def _run_server():
    """Start uvicorn in a subprocess."""
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.abspath(DB_PATH)}"
    os.environ["JWT_SECRET_KEY"] = "e2e-test-secret"
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8877, log_level="warning")


@pytest.fixture(scope="module")
def server():
    """Launch the API server for the test module, teardown after."""
    for f in [DB_PATH, DB_PATH + "-wal", DB_PATH + "-shm", DB_PATH + "-journal"]:
        if os.path.exists(f):
            os.unlink(f)

    proc = multiprocessing.Process(target=_run_server, daemon=True)
    proc.start()

    import httpx
    for _ in range(30):
        try:
            resp = httpx.get(f"{BASE_URL}/health", timeout=1)
            if resp.status_code == 200:
                break
        except (httpx.ConnectError, httpx.ReadTimeout):
            pass
        time.sleep(0.3)
    else:
        proc.terminate()
        pytest.fail("Server did not start in time")

    yield BASE_URL

    proc.terminate()
    proc.join(timeout=5)
    for f in [DB_PATH, DB_PATH + "-wal", DB_PATH + "-shm", DB_PATH + "-journal"]:
        if os.path.exists(f):
            os.unlink(f)


@pytest.fixture(scope="module")
def browser_page(server):
    """Single browser page with video recording at 1920x1080."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("playwright not installed")

    os.makedirs(VIDEO_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=350)
        context = browser.new_context(
            record_video_dir=VIDEO_DIR,
            record_video_size={"width": 1920, "height": 1080},
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        page.goto(f"{server}/dashboard")
        yield page
        context.close()
        browser.close()

    # Convert WebM → MP4
    if shutil.which("ffmpeg"):
        for webm in globmod.glob(os.path.join(VIDEO_DIR, "*.webm")):
            mp4 = webm.rsplit(".", 1)[0] + ".mp4"
            subprocess.run(
                ["ffmpeg", "-y", "-i", webm, "-c:v", "libx264", "-preset", "fast",
                 "-crf", "23", "-an", mp4],
                capture_output=True,
            )
            if os.path.exists(mp4):
                os.remove(webm)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login(page, server):
    """Log in and wait for sidebar tabs to fully enable."""
    page.goto(f"{server}/dashboard")
    page.wait_for_load_state("networkidle")
    page.locator("#login-email").fill(TEST_EMAIL)
    page.locator("#login-password").fill(TEST_PASSWORD)
    page.locator("#btn-login").click()
    page.locator("#section-profile").wait_for(state="visible", timeout=10000)
    page.wait_for_timeout(3000)


# ═══════════════════════════════════════════════════════════════════════════
#  E2E FLOW — tests run in order, each builds on the previous state
# ═══════════════════════════════════════════════════════════════════════════


# ── 1. Dashboard loads ────────────────────────────────────────────────────

def test_01_dashboard_loads_with_login_form(server, browser_page):
    """Dashboard loads and shows login form by default (not signup)."""
    page = browser_page
    page.goto(f"{server}/dashboard")
    assert page.title() == "Banking Service Dashboard"
    # Login form visible, signup form hidden
    assert page.locator("#auth-login").is_visible()
    assert not page.locator("#auth-signup").is_visible()
    assert page.locator("#login-email").is_visible()


def test_02_guided_steps_visible(server, browser_page):
    """Guided flow rail shows 6 steps."""
    page = browser_page
    steps = page.locator(".step")
    assert steps.count() == 6


def test_03_banking_tabs_disabled_before_login(server, browser_page):
    """Sidebar banking tabs are disabled before authentication."""
    page = browser_page
    for tab in ["accounts", "transfers", "cards", "statements"]:
        assert "disabled" in page.locator(f"[data-tab='{tab}']").get_attribute("class")


# ── 2. Auth edge cases ───────────────────────────────────────────────────

def test_04_signup_weak_password_rejected(server, browser_page):
    """Signup with a weak password shows error toast."""
    page = browser_page
    page.goto(f"{server}/dashboard")
    page.wait_for_load_state("networkidle")
    # Switch to signup mode
    page.locator("#auth-tab-signup").click()
    page.wait_for_timeout(300)
    assert page.locator("#auth-signup").is_visible()

    page.locator("#signup-email").fill("weak@example.com")
    page.locator("#signup-password").fill("weak")
    page.locator("#btn-signup").click()
    page.wait_for_timeout(1500)

    # Should see error toast
    toasts = page.locator(".toast-danger")
    assert toasts.count() > 0


def test_05_signup_success(server, browser_page):
    """User can sign up and sees a success toast."""
    page = browser_page
    page.goto(f"{server}/dashboard")
    page.wait_for_load_state("networkidle")
    page.locator("#auth-tab-signup").click()
    page.wait_for_timeout(300)

    page.locator("#signup-email").fill(TEST_EMAIL)
    page.locator("#signup-password").fill(TEST_PASSWORD)
    page.locator("#btn-signup").click()
    page.wait_for_timeout(2000)

    # Should see success indication
    body = page.locator("body").inner_text().lower()
    assert "created" in body or "success" in body or "log in" in body


def test_06_signup_duplicate_email_rejected(server, browser_page):
    """Duplicate signup shows error."""
    page = browser_page
    page.goto(f"{server}/dashboard")
    page.wait_for_load_state("networkidle")
    page.locator("#auth-tab-signup").click()
    page.wait_for_timeout(300)

    page.locator("#signup-email").fill(TEST_EMAIL)
    page.locator("#signup-password").fill(TEST_PASSWORD)
    page.locator("#btn-signup").click()
    page.wait_for_timeout(1500)

    toasts = page.locator(".toast-danger")
    assert toasts.count() > 0


def test_07_login_wrong_password_rejected(server, browser_page):
    """Login with wrong password shows error."""
    page = browser_page
    page.goto(f"{server}/dashboard")
    page.wait_for_load_state("networkidle")

    page.locator("#login-email").fill(TEST_EMAIL)
    page.locator("#login-password").fill("WrongPassword999!")
    page.locator("#btn-login").click()
    page.wait_for_timeout(1500)

    toasts = page.locator(".toast-danger")
    assert toasts.count() > 0


def test_08_login_nonexistent_user_rejected(server, browser_page):
    """Login with non-existent email shows error."""
    page = browser_page
    page.goto(f"{server}/dashboard")
    page.wait_for_load_state("networkidle")

    page.locator("#login-email").fill("ghost@example.com")
    page.locator("#login-password").fill("SomePass123!")
    page.locator("#btn-login").click()
    page.wait_for_timeout(1500)

    toasts = page.locator(".toast-danger")
    assert toasts.count() > 0


# ── 3. Login + Profile ───────────────────────────────────────────────────

def test_09_login_success(server, browser_page):
    """User can log in and is taken to profile page."""
    page = browser_page
    page.goto(f"{server}/dashboard")
    page.wait_for_load_state("networkidle")

    page.locator("#login-email").fill(TEST_EMAIL)
    page.locator("#login-password").fill(TEST_PASSWORD)
    page.locator("#btn-login").click()
    page.wait_for_timeout(2500)

    # User bar visible, profile section shown
    assert page.locator("#user-bar").is_visible()
    assert page.locator("#section-profile").is_visible()


def test_10_create_profile(server, browser_page):
    """User can create an account holder profile."""
    page = browser_page
    _login(page, server)

    profile_form = page.locator("#profile-form")
    profile_view = page.locator("#profile-view")

    if profile_view.is_visible():
        assert "E2E" in profile_view.inner_text()
        return

    assert profile_form.is_visible()
    page.locator("#pf-first").fill("E2E")
    page.locator("#pf-last").fill("Tester")
    page.locator("#pf-dob").fill("1990-06-15")
    page.locator("#btn-profile").click()
    page.wait_for_timeout(2000)

    body = page.locator("body").inner_text()
    assert "E2E" in body and "Tester" in body


def test_11_profile_view_shows_name(server, browser_page):
    """Profile view mode shows the holder name."""
    page = browser_page
    _login(page, server)
    page.wait_for_timeout(1000)
    assert page.locator("#pv-name").inner_text() == "E2E Tester"


# ── 4. Accounts ──────────────────────────────────────────────────────────

def test_12_create_checking_account(server, browser_page):
    """User can create a checking account."""
    page = browser_page
    _login(page, server)
    page.evaluate("showTab('accounts')")
    page.wait_for_timeout(500)

    page.locator("#new-acct-type").select_option("checking")
    page.locator("button:has-text('Open Account')").click()
    page.wait_for_timeout(1500)

    body = page.locator("#acct-tbody").inner_text().lower()
    assert "checking" in body


def test_13_create_savings_account(server, browser_page):
    """User can create a savings account."""
    page = browser_page
    _login(page, server)
    page.evaluate("showTab('accounts')")
    page.wait_for_timeout(500)

    page.locator("#new-acct-type").select_option("savings")
    page.locator("button:has-text('Open Account')").click()
    page.wait_for_timeout(1500)

    body = page.locator("#acct-tbody").inner_text().lower()
    assert "savings" in body


def test_14_account_cards_visible(server, browser_page):
    """Account visual cards are rendered."""
    page = browser_page
    _login(page, server)
    page.evaluate("showTab('accounts')")
    page.wait_for_timeout(1000)
    assert page.locator(".acct-card").count() >= 2


# ── 5. Transfers + edge cases ────────────────────────────────────────────

def test_15_deposit_funds(server, browser_page):
    """User can deposit money into checking."""
    page = browser_page
    _login(page, server)
    page.evaluate("showTab('transfers')")
    page.wait_for_timeout(1000)

    page.locator("#dep-amt").fill("5000.00")
    page.locator("#xfer-deposit button.btn-success").click()
    page.wait_for_timeout(2000)

    body = page.locator("body").inner_text().lower()
    assert "deposited" in body or "$5000" in body or "5,000" in body or "success" in body


def test_16_transfer_to_same_account_rejected(server, browser_page):
    """Transfer to the same account shows error."""
    page = browser_page
    _login(page, server)
    page.evaluate("showTab('transfers')")
    page.wait_for_timeout(500)
    page.evaluate("showXferTab('transfer')")
    page.wait_for_timeout(500)

    # Both from and to default to same (first) account
    page.locator("#xfer-amt").fill("100.00")
    page.locator("#xfer-transfer button.btn-primary").click()
    page.wait_for_timeout(1500)

    body = page.locator("body").inner_text().lower()
    assert "same account" in body


def test_17_transfer_success(server, browser_page):
    """User can transfer between checking and savings."""
    page = browser_page
    _login(page, server)
    page.evaluate("showTab('transfers')")
    page.wait_for_timeout(500)
    page.evaluate("showXferTab('transfer')")
    page.wait_for_timeout(500)

    # Select savings as destination
    page.locator("#xfer-to").select_option(index=1)
    page.locator("#xfer-amt").fill("1000.00")
    page.locator("#xfer-transfer button.btn-primary").click()
    page.wait_for_timeout(2000)

    body = page.locator("body").inner_text().lower()
    assert "transferred" in body or "$1000" in body or "1,000" in body or "success" in body


def test_18_transaction_history_populated(server, browser_page):
    """Transaction history shows deposit and transfer entries."""
    page = browser_page
    _login(page, server)
    page.evaluate("showTab('transfers')")
    page.wait_for_timeout(500)
    page.evaluate("showXferTab('history')")
    page.wait_for_timeout(1500)

    rows = page.locator("#txn-tbody tr")
    assert rows.count() >= 1


def test_19_all_transfers_list(server, browser_page):
    """All transfers page shows the transfer record."""
    page = browser_page
    _login(page, server)
    page.evaluate("showTab('transfers')")
    page.wait_for_timeout(500)
    page.evaluate("showXferTab('all-transfers')")
    page.wait_for_timeout(1500)

    rows = page.locator("#transfer-tbody tr:not(.empty-row)")
    assert rows.count() >= 1


# ── 6. Cards + edge cases ────────────────────────────────────────────────

def test_20_issue_card(server, browser_page):
    """User can issue a debit card."""
    page = browser_page
    _login(page, server)
    page.evaluate("showTab('cards')")
    page.wait_for_timeout(1000)

    page.locator("button:has-text('Issue Card')").click()
    page.wait_for_timeout(1500)

    assert page.locator("#card-tbody tr:not(.empty-row)").count() >= 1


def test_21_card_visual_displayed(server, browser_page):
    """Visual credit card component is rendered."""
    page = browser_page
    _login(page, server)
    page.evaluate("showTab('cards')")
    page.wait_for_timeout(1500)

    visuals = page.locator(".cc-visual")
    assert visuals.count() >= 1
    text = visuals.first.inner_text()
    assert "****" in text or "\u2022" in text


def test_22_card_spend_success(server, browser_page):
    """User can charge a card at a merchant."""
    page = browser_page
    _login(page, server)
    page.evaluate("showTab('cards')")
    page.wait_for_timeout(1500)

    page.locator("#spend-amt").fill("75.50")
    page.locator("#spend-merch").fill("E2E Coffee Shop")
    page.locator("button:has-text('Charge Card')").click()
    page.wait_for_timeout(1500)

    body = page.locator("body").inner_text().lower()
    assert "charged" in body or "$75" in body or "coffee" in body or "success" in body


def test_23_card_spend_insufficient_funds(server, browser_page):
    """Card spend exceeding balance is rejected."""
    page = browser_page
    _login(page, server)
    page.evaluate("showTab('cards')")
    page.wait_for_timeout(1500)

    page.locator("#spend-amt").fill("999999.99")
    page.locator("#spend-merch").fill("Too Expensive Store")
    page.locator("button:has-text('Charge Card')").click()
    page.wait_for_timeout(1500)

    body = page.locator("body").inner_text().lower()
    assert "insufficient" in body or "funds" in body or "error" in body


def test_24_block_card(server, browser_page):
    """User can block an active card."""
    page = browser_page
    _login(page, server)
    page.evaluate("showTab('cards')")
    page.wait_for_timeout(1500)

    block_btn = page.locator("button:has-text('Block')")
    if block_btn.count() > 0:
        block_btn.first.click()
        page.wait_for_timeout(1500)
        body = page.locator("#card-tbody").inner_text().lower()
        assert "blocked" in body


def test_25_card_spend_on_blocked_card_rejected(server, browser_page):
    """Card spend on a blocked card is rejected."""
    page = browser_page
    _login(page, server)
    page.evaluate("showTab('cards')")
    page.wait_for_timeout(1500)

    page.locator("#spend-amt").fill("10.00")
    page.locator("#spend-merch").fill("Should Fail")
    page.locator("button:has-text('Charge Card')").click()
    page.wait_for_timeout(1500)

    body = page.locator("body").inner_text().lower()
    assert "blocked" in body or "inactive" in body or "error" in body or "not active" in body


# ── 7. Statements ────────────────────────────────────────────────────────

def test_26_generate_statement(server, browser_page):
    """User can generate an account statement."""
    page = browser_page
    _login(page, server)
    page.evaluate("showTab('statements')")
    page.wait_for_timeout(1000)

    page.locator("button:has-text('Generate Statement')").click()
    page.wait_for_timeout(1500)

    body = page.locator("body").inner_text().lower()
    assert "statement" in body or "transaction" in body


def test_27_statement_detail_shows_financials(server, browser_page):
    """Statement detail card shows opening/closing balances."""
    page = browser_page
    _login(page, server)
    page.evaluate("showTab('statements')")
    page.wait_for_timeout(500)

    page.locator("button:has-text('Generate Statement')").click()
    page.wait_for_timeout(1500)

    detail = page.locator("#stmt-detail-card")
    assert detail.is_visible()
    text = detail.inner_text().lower()
    assert "opening" in text or "closing" in text or "credits" in text


def test_28_statement_history_populated(server, browser_page):
    """Statement history table shows previously generated statements."""
    page = browser_page
    _login(page, server)
    page.evaluate("showTab('statements')")
    page.wait_for_timeout(1500)

    rows = page.locator("#stmt-tbody tr:not(.empty-row)")
    assert rows.count() >= 1


# ── 8. Dashboard overview ────────────────────────────────────────────────

def test_29_dashboard_overview_stats(server, browser_page):
    """Dashboard shows total balance and account summary."""
    page = browser_page
    _login(page, server)
    page.evaluate("showTab('dashboard')")
    page.wait_for_timeout(2000)

    stats = page.locator(".stat-card")
    assert stats.count() >= 3

    body = page.locator("#dash-stats").inner_text().lower()
    assert "total balance" in body
    assert "$" in body


# ── 9. Theme + Ops ───────────────────────────────────────────────────────

def test_30_theme_toggle(server, browser_page):
    """Dark/light theme toggle switches correctly."""
    page = browser_page
    _login(page, server)

    initial = page.evaluate("document.documentElement.getAttribute('data-theme')")
    page.locator("#theme-toggle").click()
    page.wait_for_timeout(300)
    toggled = page.evaluate("document.documentElement.getAttribute('data-theme')")
    assert toggled != initial

    # Toggle back
    page.locator("#theme-toggle").click()
    page.wait_for_timeout(300)


def test_31_ops_panel_shows_api_log(server, browser_page):
    """Ops panel shows logged API requests."""
    page = browser_page
    _login(page, server)

    page.locator("#ops-toggle").click()
    page.wait_for_timeout(500)
    assert page.locator("#ops-panel").is_visible()

    rows = page.locator("#ops-tbody tr")
    assert rows.count() > 0

    page.locator("#ops-toggle").click()
    page.wait_for_timeout(300)


# ── 10. Logout ───────────────────────────────────────────────────────────

def test_32_logout_returns_to_auth(server, browser_page):
    """Logout returns to auth screen with disabled tabs."""
    page = browser_page
    _login(page, server)

    page.locator("#logout-btn").click()
    page.wait_for_timeout(1500)

    assert page.locator("#section-auth").is_visible()
    assert "disabled" in page.locator("[data-tab='accounts']").get_attribute("class")


# ── 11. API sanity from browser ──────────────────────────────────────────

def test_33_api_health(server, browser_page):
    """Health endpoint responds from browser context."""
    page = browser_page
    result = page.evaluate(f"""
        async () => {{
            const resp = await fetch('{server}/health');
            return await resp.json();
        }}
    """)
    assert result.get("status") == "healthy"


def test_34_api_ready(server, browser_page):
    """Readiness endpoint responds from browser context."""
    page = browser_page
    result = page.evaluate(f"""
        async () => {{
            const resp = await fetch('{server}/ready');
            return await resp.json();
        }}
    """)
    assert result.get("status") == "ready"
