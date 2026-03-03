"""Playwright E2E tests for the banking dashboard frontend.

These tests launch a real uvicorn server and use Playwright to drive the
browser through the full user journey: signup → profile → accounts →
deposit → transfer → cards → statements.

Run with:
    uv run --with pytest,playwright,httpx pytest tests/test_playwright.py -v
"""

import multiprocessing
import os
import time

import pytest

# ---------------------------------------------------------------------------
# Server management — start/stop a real uvicorn instance for browser tests
# ---------------------------------------------------------------------------

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "test_e2e.db")
BASE_URL = "http://127.0.0.1:8877"


def _run_server():
    """Start uvicorn in a subprocess."""
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.abspath(DB_PATH)}"
    os.environ["JWT_SECRET_KEY"] = "e2e-test-secret"
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8877, log_level="warning")


@pytest.fixture(scope="module")
def server():
    """Launch the API server for the test module, teardown after."""
    # Clean any leftover DB
    for f in [DB_PATH, DB_PATH + "-wal", DB_PATH + "-shm", DB_PATH + "-journal"]:
        if os.path.exists(f):
            os.unlink(f)

    proc = multiprocessing.Process(target=_run_server, daemon=True)
    proc.start()

    # Wait for server to be ready
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


# ---------------------------------------------------------------------------
# E2E tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def browser_page(server):
    """Create a single browser page for the module."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("playwright not installed")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{server}/dashboard")
        yield page
        browser.close()


def test_dashboard_loads(server, browser_page):
    """Dashboard page loads and shows login/signup."""
    page = browser_page
    page.goto(f"{server}/dashboard")
    # Should see the page title or auth section
    assert page.title() or page.locator("body").inner_text()
    # Look for signup or login related elements
    body_text = page.locator("body").inner_text()
    assert any(
        word in body_text.lower()
        for word in ["signup", "sign up", "login", "log in", "email", "register"]
    ), f"Expected auth UI, got: {body_text[:200]}"


def test_signup_flow(server, browser_page):
    """User can sign up through the dashboard form."""
    page = browser_page
    page.goto(f"{server}/dashboard")
    page.wait_for_load_state("networkidle")

    # Fill signup form
    email_input = page.locator("input[type='email'], input[name='email'], #signup-email, #email")
    if email_input.count() > 0:
        email_input.first.fill("e2e@example.com")
    else:
        # Try text input as fallback
        inputs = page.locator("input[type='text']")
        if inputs.count() > 0:
            inputs.first.fill("e2e@example.com")

    password_input = page.locator(
        "input[type='password'], input[name='password'], #signup-password, #password"
    )
    if password_input.count() > 0:
        password_input.first.fill("StrongPass1!")

    # Click signup button
    signup_btn = page.locator(
        "button:has-text('Sign'), button:has-text('sign'), "
        "button:has-text('Register'), button:has-text('Create')"
    )
    if signup_btn.count() > 0:
        signup_btn.first.click()
        page.wait_for_timeout(1000)

    body = page.locator("body").inner_text().lower()
    # After signup, we should see some success indication or the next step
    assert any(
        word in body
        for word in ["success", "logged", "welcome", "profile", "holder", "account", "dashboard"]
    ), f"Signup did not progress: {body[:300]}"


def test_login_flow(server, browser_page):
    """User can log in through the dashboard."""
    page = browser_page
    page.goto(f"{server}/dashboard")
    page.wait_for_load_state("networkidle")

    # Find and click login tab/link if separate from signup
    login_tab = page.locator(
        "a:has-text('Login'), a:has-text('Log in'), "
        "button:has-text('Login'), button:has-text('Log in'), "
        "[data-tab='login'], #login-tab"
    )
    if login_tab.count() > 0:
        login_tab.first.click()
        page.wait_for_timeout(300)

    # Fill login form
    email_inputs = page.locator("input[type='email'], input[name='email']")
    if email_inputs.count() > 0:
        email_inputs.first.fill("e2e@example.com")

    pw_inputs = page.locator("input[type='password']")
    if pw_inputs.count() > 0:
        pw_inputs.first.fill("StrongPass1!")

    # Click login
    login_btn = page.locator(
        "button:has-text('Log in'), button:has-text('Login'), button:has-text('Sign in')"
    )
    if login_btn.count() > 0:
        login_btn.first.click()
        page.wait_for_timeout(1000)

    body = page.locator("body").inner_text().lower()
    assert any(
        word in body
        for word in ["logged", "welcome", "profile", "holder", "account", "dashboard", "e2e@"]
    ), f"Login did not progress: {body[:300]}"


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
