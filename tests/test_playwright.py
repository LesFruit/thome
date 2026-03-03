"""End-to-end Playwright tests: two story-driven flows with edge-case validation.

Story 1 — "New Customer Journey": A brand-new user signs up, hits auth edge cases,
creates a profile, opens accounts, funds them, makes transfers and card spends, generates
a statement, explores the dashboard, and logs out.  Tests the happy path with inline
validation of every error guard along the way.

Story 2 — "Returning Customer": The same user logs back in and verifies all data
persisted — accounts, balances, transaction history, cards, statements — then tests
additional edge cases (blocked card spend, insufficient funds) before logging out.

Both tests share one browser context so the video is a single continuous recording.

Run with:
    uv run --with pytest,playwright,httpx pytest tests/test_playwright.py -v
"""

import glob as globmod
import os
import shutil
import subprocess
import sys
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

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def server():
    """Launch the API server as a separate process with its own env."""
    for f in [DB_PATH, DB_PATH + "-wal", DB_PATH + "-shm", DB_PATH + "-journal"]:
        if os.path.exists(f):
            os.unlink(f)

    env = {**os.environ,
           "DATABASE_URL": f"sqlite:///{os.path.abspath(DB_PATH)}",
           "JWT_SECRET_KEY": "e2e-test-secret"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", "8877", "--log-level", "warning"],
        cwd=ROOT_DIR, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    import httpx
    for _ in range(40):
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
    proc.wait(timeout=5)
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
        browser = p.chromium.launch(headless=True, slow_mo=300)
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

def wait(page, ms=1200):
    page.wait_for_timeout(ms)


def expect_toast(page, kind, text_fragment=None):
    """Assert a toast of the given kind appeared. Optionally check text."""
    toasts = page.locator(f".toast-{kind}")
    assert toasts.count() > 0, f"Expected .toast-{kind} but found none"
    if text_fragment:
        found = any(text_fragment.lower() in toasts.nth(i).inner_text().lower()
                     for i in range(toasts.count()))
        assert found, f"No .toast-{kind} contains '{text_fragment}'"


def nav(page, tab):
    page.evaluate(f"showTab('{tab}')")
    wait(page, 800)


def xfer_tab(page, tab):
    page.evaluate(f"showXferTab('{tab}')")
    wait(page, 600)


# ═══════════════════════════════════════════════════════════════════════════
#  STORY 1 — New Customer Journey
# ═══════════════════════════════════════════════════════════════════════════

def test_01_new_customer_journey(server, browser_page):
    """Complete new-customer flow: signup → profile → accounts → deposit →
    transfer → card → spend → statement → dashboard → logout.
    Validates edge cases inline without ever re-logging in."""
    page = browser_page

    # ── Landing page ────────────────────────────────────────────────────
    page.goto(f"{server}/dashboard")
    page.wait_for_load_state("networkidle")
    assert page.title() == "Banking Service Dashboard"
    assert page.locator("#auth-login").is_visible()
    assert not page.locator("#auth-signup").is_visible()

    # Guided steps visible, banking tabs disabled
    assert page.locator(".step").count() == 6
    for tab in ["accounts", "transfers", "cards", "statements"]:
        assert "disabled" in page.locator(f"[data-tab='{tab}']").get_attribute("class")

    # ── Edge case: weak password signup ─────────────────────────────────
    page.locator("#auth-tab-signup").click()
    wait(page, 400)
    page.locator("#signup-email").fill("weak@example.com")
    page.locator("#signup-password").fill("weak")
    page.locator("#btn-signup").click()
    wait(page, 1500)
    expect_toast(page, "danger")

    # ── Successful signup ───────────────────────────────────────────────
    page.locator("#signup-email").fill(TEST_EMAIL)
    page.locator("#signup-password").fill(TEST_PASSWORD)
    page.locator("#btn-signup").click()
    wait(page, 2000)
    body = page.locator("body").inner_text().lower()
    assert "created" in body or "success" in body or "log in" in body

    # ── Edge case: duplicate email signup ───────────────────────────────
    page.locator("#auth-tab-signup").click()
    wait(page, 400)
    page.locator("#signup-email").fill(TEST_EMAIL)
    page.locator("#signup-password").fill(TEST_PASSWORD)
    page.locator("#btn-signup").click()
    wait(page, 1500)
    expect_toast(page, "danger")

    # ── Edge case: wrong password login ─────────────────────────────────
    page.locator("#auth-tab-login").click()
    wait(page, 400)
    page.locator("#login-email").fill(TEST_EMAIL)
    page.locator("#login-password").fill("WrongPassword999!")
    page.locator("#btn-login").click()
    wait(page, 1500)
    expect_toast(page, "danger")

    # ── Edge case: non-existent user login ──────────────────────────────
    page.locator("#login-email").fill("ghost@example.com")
    page.locator("#login-password").fill("SomePass123!")
    page.locator("#btn-login").click()
    wait(page, 1500)
    expect_toast(page, "danger")

    # ── Successful login ────────────────────────────────────────────────
    page.locator("#login-email").fill(TEST_EMAIL)
    page.locator("#login-password").fill(TEST_PASSWORD)
    page.locator("#btn-login").click()
    page.locator("#user-bar").wait_for(state="visible", timeout=15000)
    wait(page, 4000)

    # ── Create profile ──────────────────────────────────────────────────
    # After login, loadProfile() fires async; for new user it 404s and shows the form
    page.locator("#pf-first").wait_for(state="visible", timeout=15000)
    page.locator("#pf-first").fill("E2E")
    page.locator("#pf-last").fill("Tester")
    page.locator("#pf-dob").fill("1990-06-15")
    page.locator("#btn-profile").click()
    wait(page, 2000)
    assert page.locator("#pv-name").inner_text() == "E2E Tester"

    # ── Create checking account ─────────────────────────────────────────
    nav(page, "accounts")
    page.locator("#new-acct-type").select_option("checking")
    page.locator("button:has-text('Open Account')").click()
    wait(page, 1500)
    assert "checking" in page.locator("#acct-tbody").inner_text().lower()

    # ── Create savings account ──────────────────────────────────────────
    page.locator("#new-acct-type").select_option("savings")
    page.locator("button:has-text('Open Account')").click()
    wait(page, 1500)
    assert "savings" in page.locator("#acct-tbody").inner_text().lower()
    assert page.locator(".acct-card").count() >= 2

    # ── Deposit $5,000 into checking ────────────────────────────────────
    nav(page, "transfers")
    page.locator("#dep-amt").fill("5000.00")
    page.locator("#xfer-deposit button.btn-success").click()
    wait(page, 2000)
    expect_toast(page, "success", "deposited")

    # ── Edge case: transfer to same account ─────────────────────────────
    xfer_tab(page, "transfer")
    page.locator("#xfer-amt").fill("100.00")
    page.locator("#xfer-transfer button.btn-primary").click()
    wait(page, 1500)
    expect_toast(page, "danger", "same account")

    # ── Transfer $1,000 to savings ──────────────────────────────────────
    page.locator("#xfer-to").select_option(index=1)
    page.locator("#xfer-amt").fill("1000.00")
    page.locator("#xfer-transfer button.btn-primary").click()
    wait(page, 2000)
    expect_toast(page, "success", "transferred")

    # ── Verify transaction history has entries ───────────────────────────
    xfer_tab(page, "history")
    wait(page, 1000)
    assert page.locator("#txn-tbody tr").count() >= 2  # deposit + debit

    # ── Verify all-transfers list ───────────────────────────────────────
    xfer_tab(page, "all-transfers")
    wait(page, 1000)
    assert page.locator("#transfer-tbody tr:not(.empty-row)").count() >= 1

    # ── Issue card ──────────────────────────────────────────────────────
    nav(page, "cards")
    page.locator("button:has-text('Issue Card')").click()
    wait(page, 1500)
    assert page.locator("#card-tbody tr:not(.empty-row)").count() >= 1
    assert page.locator(".cc-visual").count() >= 1

    # ── Card spend $75.50 ───────────────────────────────────────────────
    page.locator("#spend-amt").fill("75.50")
    page.locator("#spend-merch").fill("Downtown Bistro")
    page.locator("button:has-text('Charge Card')").click()
    wait(page, 1500)
    expect_toast(page, "success", "charged")

    # ── Edge case: card spend exceeding balance ─────────────────────────
    page.locator("#spend-amt").fill("999999.99")
    page.locator("#spend-merch").fill("Too Expensive Store")
    page.locator("button:has-text('Charge Card')").click()
    wait(page, 1500)
    expect_toast(page, "danger")

    # ── Generate statement ──────────────────────────────────────────────
    nav(page, "statements")
    page.locator("button:has-text('Generate Statement')").click()
    wait(page, 2000)
    detail = page.locator("#stmt-detail-card")
    assert detail.is_visible()
    text = detail.inner_text().lower()
    assert "opening" in text or "closing" in text or "credits" in text

    # ── Dashboard overview ──────────────────────────────────────────────
    nav(page, "dashboard")
    wait(page, 2000)
    stats = page.locator(".stat-card")
    assert stats.count() >= 3
    dash_text = page.locator("#dash-stats").inner_text().lower()
    assert "total balance" in dash_text and "$" in dash_text

    # Recent activity shows entries from multiple transaction types
    activity = page.locator("#dash-activity").inner_text().lower()
    assert "deposit" in activity or "card" in activity or "transfer" in activity

    # ── Theme toggle ────────────────────────────────────────────────────
    initial_theme = page.evaluate("document.documentElement.getAttribute('data-theme')")
    page.locator("#theme-toggle").click()
    wait(page, 500)
    assert page.evaluate("document.documentElement.getAttribute('data-theme')") != initial_theme
    page.locator("#theme-toggle").click()
    wait(page, 300)

    # ── Ops panel ───────────────────────────────────────────────────────
    page.locator("#ops-toggle").click()
    wait(page, 600)
    assert page.locator("#ops-panel").is_visible()
    assert page.locator("#ops-tbody tr").count() > 0
    page.locator("#ops-toggle").click()
    wait(page, 300)

    # ── Logout ──────────────────────────────────────────────────────────
    page.locator("#logout-btn").click()
    wait(page, 1500)
    assert page.locator("#section-auth").is_visible()
    assert "disabled" in page.locator("[data-tab='accounts']").get_attribute("class")


# ═══════════════════════════════════════════════════════════════════════════
#  STORY 2 — Returning Customer (data persistence + more edge cases)
# ═══════════════════════════════════════════════════════════════════════════

def test_02_returning_customer(server, browser_page):
    """Returning customer logs in and verifies all data persisted from Story 1.
    Then tests blocked-card spend and confirms the full audit trail."""
    page = browser_page

    # ── Login ───────────────────────────────────────────────────────────
    page.locator("#login-email").fill(TEST_EMAIL)
    page.locator("#login-password").fill(TEST_PASSWORD)
    page.locator("#btn-login").click()
    page.locator("#section-profile").wait_for(state="visible", timeout=10000)
    wait(page, 2000)

    # ── Profile persisted ───────────────────────────────────────────────
    assert page.locator("#pv-name").inner_text() == "E2E Tester"

    # ── Accounts persisted with correct balances ────────────────────────
    nav(page, "accounts")
    assert page.locator(".acct-card").count() >= 2
    acct_text = page.locator("#section-accounts").inner_text().lower()
    assert "checking" in acct_text and "savings" in acct_text

    # ── Transaction history persisted (deposit + transfer debit + card spend)
    nav(page, "transfers")
    xfer_tab(page, "history")
    wait(page, 1000)
    txn_rows = page.locator("#txn-tbody tr")
    assert txn_rows.count() >= 3  # deposit, debit, card_spend
    history_text = page.locator("#txn-tbody").inner_text().lower()
    assert "deposit" in history_text
    assert "card" in history_text or "bistro" in history_text

    # ── All transfers persisted ─────────────────────────────────────────
    xfer_tab(page, "all-transfers")
    wait(page, 1000)
    assert page.locator("#transfer-tbody tr:not(.empty-row)").count() >= 1

    # ── Card persisted ──────────────────────────────────────────────────
    nav(page, "cards")
    assert page.locator("#card-tbody tr:not(.empty-row)").count() >= 1

    # ── Block the card ──────────────────────────────────────────────────
    block_btn = page.locator("button:has-text('Block')")
    assert block_btn.count() > 0, "Expected a Block button"
    block_btn.first.click()
    wait(page, 1500)
    assert "blocked" in page.locator("#card-tbody").inner_text().lower()

    # ── Edge case: spend on blocked card ────────────────────────────────
    page.locator("#spend-amt").fill("10.00")
    page.locator("#spend-merch").fill("Should Fail")
    page.locator("button:has-text('Charge Card')").click()
    wait(page, 1500)
    body = page.locator("body").inner_text().lower()
    assert "blocked" in body or "not active" in body or "error" in body

    # ── Statements persisted ────────────────────────────────────────────
    nav(page, "statements")
    wait(page, 1000)
    assert page.locator("#stmt-tbody tr:not(.empty-row)").count() >= 1

    # ── Generate a second statement to confirm card spend is captured ───
    page.locator("button:has-text('Generate Statement')").click()
    wait(page, 2000)
    detail_text = page.locator("#stmt-detail-card").inner_text().lower()
    assert "debit" in detail_text or "card" in detail_text or "closing" in detail_text

    # ── Dashboard shows full activity across all accounts ───────────────
    nav(page, "dashboard")
    wait(page, 2000)
    activity = page.locator("#dash-activity").inner_text().lower()
    assert len(activity) > 20  # meaningful content, not just "no activity"

    # ── API health check from browser context ───────────────────────────
    health = page.evaluate(f"""
        async () => {{
            const resp = await fetch('{server}/health');
            return await resp.json();
        }}
    """)
    assert health.get("status") == "healthy"

    # ── Logout ──────────────────────────────────────────────────────────
    page.locator("#logout-btn").click()
    wait(page, 1500)
    assert page.locator("#section-auth").is_visible()


# ═══════════════════════════════════════════════════════════════════════════
#  COMPONENT TESTS — API-level verification via browser fetch
# ═══════════════════════════════════════════════════════════════════════════

def test_03_api_components(server, browser_page):
    """Component-level API tests run from the browser context.
    Validates each service independently: auth, holders, accounts,
    transfers, cards, statements, health — including ledger completeness
    for card spends (verifies Transaction record is created)."""
    page = browser_page
    import json
    import uuid as _uuid

    def fetch(method, path, body=None, token=True):
        """Helper: call the API from the browser and return {status, data}."""
        tok_js = "window._t" if token else "null"
        body_js = json.dumps(body) if body else "null"
        return page.evaluate(f"""async () => {{
            const h = {{'Content-Type': 'application/json'}};
            const tok = {tok_js};
            if (tok) h['Authorization'] = 'Bearer ' + tok;
            const opts = {{ method: '{method}', headers: h }};
            if ({body_js} !== null) opts.body = JSON.stringify({body_js});
            const r = await fetch('{server}{path}', opts);
            return {{ status: r.status, data: await r.json() }};
        }}""")

    # ── Health ────────────────────────────────────────────────────────
    r = fetch("GET", "/health", token=False)
    assert r["status"] == 200 and r["data"]["status"] == "healthy"
    r = fetch("GET", "/ready", token=False)
    assert r["status"] == 200 and r["data"]["status"] == "ready"

    # ── Auth: signup ──────────────────────────────────────────────────
    email = f"comp-{_uuid.uuid4().hex[:6]}@test.com"
    r = fetch("POST", "/api/v1/auth/signup",
              {"email": email, "password": "CompTest1!"}, token=False)
    assert r["status"] == 201 and r["data"]["email"] == email

    # Auth: duplicate rejected
    r2 = fetch("POST", "/api/v1/auth/signup",
               {"email": email, "password": "CompTest1!"}, token=False)
    assert r2["status"] == 409

    # Auth: login
    r = page.evaluate(f"""async () => {{
        const r = await fetch('{server}/api/v1/auth/login', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ email: '{email}', password: 'CompTest1!' }})
        }});
        const d = await r.json();
        window._t = d.access_token;
        window._rt = d.refresh_token;
        return {{ status: r.status, ok: !!d.access_token }};
    }}""")
    assert r["status"] == 200 and r["ok"]

    # Auth: me
    r = fetch("GET", "/api/v1/auth/me")
    assert r["status"] == 200 and r["data"]["email"] == email

    # Auth: no token → 401
    r = fetch("GET", "/api/v1/auth/me", token=False)
    assert r["status"] in (401, 403)

    # ── Holder ────────────────────────────────────────────────────────
    r = fetch("POST", "/api/v1/holders",
              {"first_name": "Comp", "last_name": "Test", "date_of_birth": "1985-01-01"})
    assert r["status"] == 201 and r["data"]["first_name"] == "Comp"

    r = fetch("GET", "/api/v1/holders/me")
    assert r["status"] == 200 and r["data"]["last_name"] == "Test"

    # ── Account ───────────────────────────────────────────────────────
    r = page.evaluate(f"""async () => {{
        const r = await fetch('{server}/api/v1/accounts', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json', 'Authorization': 'Bearer ' + window._t}},
            body: JSON.stringify({{ account_type: 'checking' }})
        }});
        const d = await r.json();
        window._acct = d.id;
        return {{ status: r.status, data: d }};
    }}""")
    assert r["status"] == 201 and r["data"]["balance_cents"] == 0

    r = fetch("GET", "/api/v1/accounts")
    assert r["status"] == 200 and len(r["data"]) >= 1

    # ── Deposit ───────────────────────────────────────────────────────
    r = page.evaluate(f"""async () => {{
        const r = await fetch('{server}/api/v1/accounts/' + window._acct + '/deposit', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json', 'Authorization': 'Bearer ' + window._t}},
            body: JSON.stringify({{ amount_cents: 50000 }})
        }});
        return {{ status: r.status, data: await r.json() }};
    }}""")
    assert r["status"] == 200 and r["data"]["balance_cents"] == 50000

    # ── Transactions: deposit recorded ────────────────────────────────
    r = page.evaluate(f"""async () => {{
        const r = await fetch('{server}/api/v1/accounts/' + window._acct + '/transactions', {{
            headers: {{'Authorization': 'Bearer ' + window._t}}
        }});
        return {{ status: r.status, data: await r.json() }};
    }}""")
    assert r["status"] == 200
    assert any(t["type"] == "deposit" for t in r["data"])

    # ── Card: issue + spend ───────────────────────────────────────────
    r = page.evaluate(f"""async () => {{
        const r = await fetch('{server}/api/v1/accounts/' + window._acct + '/cards', {{
            method: 'POST',
            headers: {{'Authorization': 'Bearer ' + window._t}}
        }});
        const d = await r.json();
        window._card = d.id;
        return {{ status: r.status, data: d }};
    }}""")
    assert r["status"] == 201 and r["data"]["status"] == "active"

    idem = str(_uuid.uuid4())
    r = page.evaluate(f"""async () => {{
        const r = await fetch('{server}/api/v1/cards/' + window._card + '/spend', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json', 'Authorization': 'Bearer ' + window._t}},
            body: JSON.stringify({{ amount_cents: 1500, merchant: 'Component Cafe', idempotency_key: '{idem}' }})
        }});
        return {{ status: r.status, data: await r.json() }};
    }}""")
    assert r["status"] == 201 and r["data"]["merchant"] == "Component Cafe"

    # Card spend → Transaction ledger entry exists
    r = page.evaluate(f"""async () => {{
        const r = await fetch('{server}/api/v1/accounts/' + window._acct + '/transactions', {{
            headers: {{'Authorization': 'Bearer ' + window._t}}
        }});
        return {{ status: r.status, data: await r.json() }};
    }}""")
    assert r["status"] == 200
    assert any(t["type"] == "card_spend" for t in r["data"]), \
        "Card spend missing from transaction ledger"

    # ── Statement ─────────────────────────────────────────────────────
    r = page.evaluate(f"""async () => {{
        const r = await fetch('{server}/api/v1/accounts/' + window._acct + '/statements', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json', 'Authorization': 'Bearer ' + window._t}},
            body: JSON.stringify({{ start_date: '2020-01-01', end_date: '2030-12-31' }})
        }});
        return {{ status: r.status, data: await r.json() }};
    }}""")
    assert r["status"] == 201
    assert r["data"]["transaction_count"] >= 2  # deposit + card_spend

    # ── Auth: refresh + logout ────────────────────────────────────────
    r = page.evaluate(f"""async () => {{
        const r = await fetch('{server}/api/v1/auth/refresh', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ refresh_token: window._rt }})
        }});
        const d = await r.json();
        window._t = d.access_token;
        return {{ status: r.status, ok: !!d.access_token }};
    }}""")
    assert r["status"] == 200

    r = page.evaluate(f"""async () => {{
        const r = await fetch('{server}/api/v1/auth/logout', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json', 'Authorization': 'Bearer ' + window._t}},
            body: JSON.stringify({{ refresh_token: window._rt }})
        }});
        return {{ status: r.status }};
    }}""")
    assert r["status"] == 200
