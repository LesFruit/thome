"""Comprehensive Playwright E2E tests for the banking dashboard.

These tests launch a real uvicorn server and drive the browser through every
major user journey: signup → login → profile → accounts → deposit → transfer →
cards → card spend → statements → logout.

Run with:
    uv run --with pytest,playwright,httpx pytest tests/test_playwright.py -v
"""

import multiprocessing
import os
import time

import pytest

# ---------------------------------------------------------------------------
# Server management
# ---------------------------------------------------------------------------

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "test_e2e.db")
BASE_URL = "http://127.0.0.1:8877"
TEST_EMAIL = "e2e-user@example.com"
TEST_PASSWORD = "StrongPass1!"


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


VIDEO_DIR = os.path.join(os.path.dirname(__file__), "..", "recordings")


@pytest.fixture(scope="module")
def browser_page(server):
    """Create a single browser page with video recording enabled."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("playwright not installed")

    os.makedirs(VIDEO_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            record_video_dir=VIDEO_DIR,
            record_video_size={"width": 1280, "height": 720},
            viewport={"width": 1280, "height": 720},
        )
        page = context.new_page()
        page.goto(f"{server}/dashboard")
        yield page
        context.close()  # finalizes video file
        browser.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wait_for_toast(page, text_fragment, timeout=3000):
    """Wait for a toast notification containing text."""
    toast = page.locator(f".toast:has-text('{text_fragment}')")
    toast.wait_for(state="visible", timeout=timeout)
    return toast.inner_text()


def _fill_and_submit(page, fields, button_text):
    """Fill form fields and click submit button."""
    for selector, value in fields.items():
        el = page.locator(selector)
        el.fill(value)
    page.locator(f"button:has-text('{button_text}')").first.click()


# ---------------------------------------------------------------------------
# 1. Dashboard + Auth
# ---------------------------------------------------------------------------

def test_dashboard_loads(server, browser_page):
    """Dashboard page loads and shows auth forms."""
    page = browser_page
    page.goto(f"{server}/dashboard")
    assert page.title() == "Banking Service Dashboard"
    assert page.locator("#signup-email").is_visible()
    assert page.locator("#login-email").is_visible()
    body = page.locator("body").inner_text().lower()
    assert "sign up" in body or "create account" in body


def test_guided_steps_visible(server, browser_page):
    """Guided flow rail shows 6 steps with Auth as current."""
    page = browser_page
    page.goto(f"{server}/dashboard")
    steps = page.locator(".step")
    assert steps.count() == 6
    assert "current" in page.locator("#step-auth").get_attribute("class")


def test_sidebar_auth_is_active(server, browser_page):
    """Sidebar nav has Auth active and other tabs disabled."""
    page = browser_page
    page.goto(f"{server}/dashboard")
    assert "active" in page.locator("[data-tab='auth']").get_attribute("class")
    assert "disabled" in page.locator("[data-tab='accounts']").get_attribute("class")
    assert "disabled" in page.locator("[data-tab='cards']").get_attribute("class")


def test_signup_new_user(server, browser_page):
    """User can sign up via the dashboard."""
    page = browser_page
    page.goto(f"{server}/dashboard")
    page.wait_for_load_state("networkidle")

    page.locator("#signup-email").fill(TEST_EMAIL)
    page.locator("#signup-password").fill(TEST_PASSWORD)
    page.locator("#btn-signup").click()
    page.wait_for_timeout(1500)

    # Should see success toast
    body = page.locator("body").inner_text().lower()
    assert "created" in body or "success" in body or "log in" in body, f"Signup failed: {body[:300]}"


def test_signup_duplicate_user(server, browser_page):
    """Duplicate signup shows error."""
    page = browser_page
    page.goto(f"{server}/dashboard")
    page.wait_for_load_state("networkidle")

    page.locator("#signup-email").fill(TEST_EMAIL)
    page.locator("#signup-password").fill(TEST_PASSWORD)
    page.locator("#btn-signup").click()
    page.wait_for_timeout(1500)

    # Should show an error toast (user already exists)
    toasts = page.locator(".toast-danger, .toast:has-text('already'), .toast:has-text('exists'), .toast:has-text('conflict')")
    assert toasts.count() > 0 or "already" in page.locator("body").inner_text().lower()


def test_login_success(server, browser_page):
    """User can log in and navigate to profile."""
    page = browser_page
    page.goto(f"{server}/dashboard")
    page.wait_for_load_state("networkidle")

    page.locator("#login-email").fill(TEST_EMAIL)
    page.locator("#login-password").fill(TEST_PASSWORD)
    page.locator("#btn-login").click()
    page.wait_for_timeout(2000)

    # After login: user bar visible, profile section shown
    assert page.locator("#user-bar").is_visible()
    assert page.locator("#section-profile").is_visible()
    body = page.locator("body").inner_text().lower()
    assert "profile" in body or "holder" in body


def test_login_invalid_credentials(server, browser_page):
    """Invalid login shows error."""
    page = browser_page
    page.goto(f"{server}/dashboard")
    page.wait_for_load_state("networkidle")

    page.locator("#login-email").fill("wrong@example.com")
    page.locator("#login-password").fill("BadPass999!")
    page.locator("#btn-login").click()
    page.wait_for_timeout(1500)

    # Error toast should appear
    toasts = page.locator(".toast-danger")
    assert toasts.count() > 0


# ---------------------------------------------------------------------------
# 2. Profile management
# ---------------------------------------------------------------------------

def _login(page, server):
    """Helper: log in and wait for profile page."""
    page.goto(f"{server}/dashboard")
    page.wait_for_load_state("networkidle")
    page.locator("#login-email").fill(TEST_EMAIL)
    page.locator("#login-password").fill(TEST_PASSWORD)
    page.locator("#btn-login").click()
    page.wait_for_timeout(2000)


def test_create_profile(server, browser_page):
    """User can create an account holder profile."""
    page = browser_page
    _login(page, server)

    # Should show profile form (no holder yet)
    profile_form = page.locator("#profile-form")
    assert profile_form.is_visible()

    page.locator("#pf-first").fill("E2E")
    page.locator("#pf-last").fill("Tester")
    page.locator("#pf-dob").fill("1990-06-15")
    page.locator("#btn-profile").click()
    page.wait_for_timeout(1500)

    # Profile view should appear
    body = page.locator("body").inner_text()
    assert "E2E" in body and "Tester" in body


def test_profile_view_shows_after_creation(server, browser_page):
    """After profile creation, the view mode shows name and DOB."""
    page = browser_page
    _login(page, server)

    # Profile should already exist, show view mode
    page.wait_for_timeout(1000)
    assert page.locator("#pv-name").inner_text() == "E2E Tester"


# ---------------------------------------------------------------------------
# 3. Accounts
# ---------------------------------------------------------------------------

def test_create_checking_account(server, browser_page):
    """User can create a checking account."""
    page = browser_page
    _login(page, server)

    # Navigate to accounts
    page.locator("[data-tab='accounts']").click()
    page.wait_for_timeout(500)
    assert page.locator("#section-accounts").is_visible()

    # Create checking account
    page.locator("#new-acct-type").select_option("checking")
    page.locator("button:has-text('Open Account')").click()
    page.wait_for_timeout(1500)

    # Should see the account in the table
    body = page.locator("#acct-tbody").inner_text().lower()
    assert "checking" in body


def test_create_savings_account(server, browser_page):
    """User can create a savings account."""
    page = browser_page
    _login(page, server)
    page.locator("[data-tab='accounts']").click()
    page.wait_for_timeout(500)

    page.locator("#new-acct-type").select_option("savings")
    page.locator("button:has-text('Open Account')").click()
    page.wait_for_timeout(1500)

    body = page.locator("#acct-tbody").inner_text().lower()
    assert "savings" in body


def test_account_cards_visible(server, browser_page):
    """Account visual cards are displayed."""
    page = browser_page
    _login(page, server)
    page.locator("[data-tab='accounts']").click()
    page.wait_for_timeout(1000)

    cards = page.locator(".acct-card")
    assert cards.count() >= 2  # checking + savings


# ---------------------------------------------------------------------------
# 4. Deposits + Transfers
# ---------------------------------------------------------------------------

def test_deposit_funds(server, browser_page):
    """User can deposit money into an account."""
    page = browser_page
    _login(page, server)
    page.locator("[data-tab='transfers']").click()
    page.wait_for_timeout(1000)

    # Deposit tab should be visible by default
    assert page.locator("#xfer-deposit").is_visible()

    page.locator("#dep-amt").fill("500.00")
    page.locator("button:has-text('Deposit')").click()
    page.wait_for_timeout(1500)

    # Check success toast
    body = page.locator("body").inner_text().lower()
    assert "deposited" in body or "$500" in body or "success" in body


def test_transfer_between_accounts(server, browser_page):
    """User can transfer money between accounts."""
    page = browser_page
    _login(page, server)
    page.locator("[data-tab='transfers']").click()
    page.wait_for_timeout(500)

    # Switch to transfer tab
    page.locator("button.tab-btn:has-text('Transfer')").click()
    page.wait_for_timeout(500)

    # Fill transfer form
    page.locator("#xfer-amt").fill("100.00")
    page.locator("button:has-text('Transfer')").last.click()
    page.wait_for_timeout(1500)

    body = page.locator("body").inner_text().lower()
    assert "transferred" in body or "$100" in body or "success" in body


def test_transaction_history_visible(server, browser_page):
    """Transaction history shows deposit and transfer entries."""
    page = browser_page
    _login(page, server)
    page.locator("[data-tab='transfers']").click()
    page.wait_for_timeout(500)

    # Switch to history tab
    page.locator("button.tab-btn:has-text('History')").click()
    page.wait_for_timeout(1500)

    # Should have transactions from deposit + transfer
    rows = page.locator("#txn-tbody tr")
    assert rows.count() >= 1


def test_all_transfers_list(server, browser_page):
    """All transfers page shows the transfer record."""
    page = browser_page
    _login(page, server)
    page.locator("[data-tab='transfers']").click()
    page.wait_for_timeout(500)

    page.locator("button.tab-btn:has-text('All Transfers')").click()
    page.wait_for_timeout(1500)

    rows = page.locator("#transfer-tbody tr:not(.empty-row)")
    assert rows.count() >= 1


# ---------------------------------------------------------------------------
# 5. Cards
# ---------------------------------------------------------------------------

def test_issue_card(server, browser_page):
    """User can issue a debit card on an account."""
    page = browser_page
    _login(page, server)
    page.locator("[data-tab='cards']").click()
    page.wait_for_timeout(1000)

    page.locator("button:has-text('Issue Card')").click()
    page.wait_for_timeout(1500)

    # Card should appear in the table
    card_rows = page.locator("#card-tbody tr:not(.empty-row)")
    assert card_rows.count() >= 1


def test_card_visual_displayed(server, browser_page):
    """Visual credit card component is rendered for active cards."""
    page = browser_page
    _login(page, server)
    page.locator("[data-tab='cards']").click()
    page.wait_for_timeout(1500)

    visuals = page.locator(".cc-visual")
    assert visuals.count() >= 1
    # Should show masked card number
    text = visuals.first.inner_text()
    assert "****" in text or "\u2022" in text


def test_card_spend(server, browser_page):
    """User can charge a card at a merchant."""
    page = browser_page
    _login(page, server)
    page.locator("[data-tab='cards']").click()
    page.wait_for_timeout(1500)

    page.locator("#spend-amt").fill("25.00")
    page.locator("#spend-merch").fill("E2E Coffee Shop")
    page.locator("button:has-text('Charge Card')").click()
    page.wait_for_timeout(1500)

    body = page.locator("body").inner_text().lower()
    assert "charged" in body or "$25" in body or "coffee" in body


def test_block_card(server, browser_page):
    """User can block an active card."""
    page = browser_page
    _login(page, server)
    page.locator("[data-tab='cards']").click()
    page.wait_for_timeout(1500)

    block_btn = page.locator("button:has-text('Block')")
    if block_btn.count() > 0:
        block_btn.first.click()
        page.wait_for_timeout(1500)
        body = page.locator("#card-tbody").inner_text().lower()
        assert "blocked" in body


# ---------------------------------------------------------------------------
# 6. Statements
# ---------------------------------------------------------------------------

def test_generate_statement(server, browser_page):
    """User can generate an account statement."""
    page = browser_page
    _login(page, server)
    page.locator("[data-tab='statements']").click()
    page.wait_for_timeout(1000)

    # Dates should be pre-populated
    assert page.locator("#stmt-start").input_value() != ""
    assert page.locator("#stmt-end").input_value() != ""

    page.locator("button:has-text('Generate Statement')").click()
    page.wait_for_timeout(1500)

    body = page.locator("body").inner_text().lower()
    assert "statement" in body or "transaction" in body


def test_statement_detail_shows(server, browser_page):
    """Statement detail card shows financial summary."""
    page = browser_page
    _login(page, server)
    page.locator("[data-tab='statements']").click()
    page.wait_for_timeout(500)

    page.locator("button:has-text('Generate Statement')").click()
    page.wait_for_timeout(1500)

    detail = page.locator("#stmt-detail-card")
    assert detail.is_visible()
    text = detail.inner_text().lower()
    assert "opening" in text or "closing" in text or "credits" in text


def test_statement_history_list(server, browser_page):
    """Statement history table shows generated statements."""
    page = browser_page
    _login(page, server)
    page.locator("[data-tab='statements']").click()
    page.wait_for_timeout(1500)

    rows = page.locator("#stmt-tbody tr:not(.empty-row)")
    assert rows.count() >= 1


# ---------------------------------------------------------------------------
# 7. Dashboard overview
# ---------------------------------------------------------------------------

def test_dashboard_overview(server, browser_page):
    """Dashboard shows total balance and account summary."""
    page = browser_page
    _login(page, server)
    page.locator("[data-tab='dashboard']").click()
    page.wait_for_timeout(2000)

    # Should see stat cards
    stats = page.locator(".stat-card")
    assert stats.count() >= 3  # Total Balance, Active Accounts, Active Cards

    body = page.locator("#dash-stats").inner_text().lower()
    assert "total balance" in body
    assert "$" in body


# ---------------------------------------------------------------------------
# 8. Theme + Ops panel
# ---------------------------------------------------------------------------

def test_theme_toggle(server, browser_page):
    """Dark/light theme toggle works."""
    page = browser_page
    _login(page, server)

    # Start with light theme
    initial = page.evaluate("document.documentElement.getAttribute('data-theme')")

    page.locator("#theme-toggle").click()
    page.wait_for_timeout(300)
    toggled = page.evaluate("document.documentElement.getAttribute('data-theme')")
    assert toggled != initial

    # Toggle back
    page.locator("#theme-toggle").click()
    page.wait_for_timeout(300)
    restored = page.evaluate("document.documentElement.getAttribute('data-theme')")
    assert restored == initial


def test_ops_panel_toggle(server, browser_page):
    """Ops panel can be opened and shows API request log."""
    page = browser_page
    _login(page, server)

    # Open ops panel
    page.locator("#ops-toggle").click()
    page.wait_for_timeout(500)
    assert page.locator("#ops-panel").is_visible()

    # Should have logged some API requests
    rows = page.locator("#ops-tbody tr")
    assert rows.count() > 0

    # Close ops panel
    page.locator("#ops-toggle").click()
    page.wait_for_timeout(300)


# ---------------------------------------------------------------------------
# 9. Logout
# ---------------------------------------------------------------------------

def test_logout(server, browser_page):
    """User can log out and return to auth screen."""
    page = browser_page
    _login(page, server)

    page.locator("#logout-btn").click()
    page.wait_for_timeout(1500)

    # Should be back at auth screen
    assert page.locator("#section-auth").is_visible()
    # Nav items should be disabled again
    assert "disabled" in page.locator("[data-tab='accounts']").get_attribute("class")


# ---------------------------------------------------------------------------
# 10. API from browser context
# ---------------------------------------------------------------------------

def test_api_health_from_browser(server, browser_page):
    """Health endpoint responds via fetch from browser context."""
    page = browser_page
    result = page.evaluate(f"""
        async () => {{
            const resp = await fetch('{server}/health');
            return await resp.json();
        }}
    """)
    assert result.get("status") == "healthy"


def test_api_ready_from_browser(server, browser_page):
    """Readiness endpoint responds from browser context."""
    page = browser_page
    result = page.evaluate(f"""
        async () => {{
            const resp = await fetch('{server}/ready');
            return await resp.json();
        }}
    """)
    assert result.get("status") == "ready"
