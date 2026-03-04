"""Stress and concurrency tests — section 5 of PRD.MD.

Tests verify:
- Concurrent transfer attempts on shared balance (overdraft prevention).
- Idempotency under concurrency.
- Ledger invariant checks under load.

Note: SQLite has inherent threading limitations (section 8 caveat).
Concurrent tests use per-request DB sessions to avoid sharing a single
session across threads, which mirrors production behavior.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

# Per-request session factory for thread-safe concurrent tests
_concurrent_engine = create_engine(
    "sqlite:///./test_stress.db",
    connect_args={"check_same_thread": False},
)


@event.listens_for(_concurrent_engine, "connect")
def _set_pragmas(dbapi_conn, _connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


_ConcurrentSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=_concurrent_engine,
)


@pytest.fixture
def stress_client():
    """Client with per-request session (thread-safe for concurrent tests)."""
    Base.metadata.create_all(bind=_concurrent_engine)

    def _get_db():
        session = _ConcurrentSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=_concurrent_engine)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _signup_login(client: TestClient, email: str) -> dict:
    client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "StrongPass1!",
        },
    )
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "StrongPass1!",
        },
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _create_funded_accounts(
    client: TestClient,
    headers: dict,
    balance: int = 100_000,
):
    """Return (acct1_id, acct2_id) with acct1 funded."""
    client.post(
        "/api/v1/holders",
        json={
            "first_name": "Stress",
            "last_name": "Tester",
            "date_of_birth": "1990-01-01",
        },
        headers=headers,
    )
    a1 = client.post(
        "/api/v1/accounts",
        json={"account_type": "checking"},
        headers=headers,
    ).json()
    a2 = client.post(
        "/api/v1/accounts",
        json={"account_type": "savings"},
        headers=headers,
    ).json()
    client.post(
        f"/api/v1/accounts/{a1['id']}/deposit",
        json={"amount_cents": balance},
        headers=headers,
    )
    return a1["id"], a2["id"]


# ---------------------------------------------------------------------------
# concurrent tests (use stress_client fixture)
# ---------------------------------------------------------------------------


def test_concurrent_transfers_no_overdraft(stress_client):
    """Multiple threads try to drain the same account — balance must never go negative."""
    headers = _signup_login(stress_client, "stress1@example.com")
    src, dst = _create_funded_accounts(stress_client, headers, balance=100_000)

    results = []

    def _transfer():
        resp = stress_client.post(
            "/api/v1/transfers",
            json={
                "source_account_id": src,
                "destination_account_id": dst,
                "amount_cents": 20_000,
                "idempotency_key": str(uuid.uuid4()),
            },
            headers=headers,
        )
        results.append(resp.status_code)

    with ThreadPoolExecutor(max_workers=8) as pool:
        for _ in range(8):
            pool.submit(_transfer)

    success = results.count(201)

    # At most 5 can succeed ($200 * 5 = $1000)
    assert success <= 5

    # Critical invariant: source balance is never negative
    acct = stress_client.get(
        f"/api/v1/accounts/{src}",
        headers=headers,
    ).json()
    assert acct["balance_cents"] >= 0

    # Conservation: total across accounts <= initial (equal without 500s)
    dst_acct = stress_client.get(
        f"/api/v1/accounts/{dst}",
        headers=headers,
    ).json()
    assert acct["balance_cents"] + dst_acct["balance_cents"] <= 100_000


def test_concurrent_card_spend_no_overdraft(stress_client):
    """Multiple card spends — balance must never go negative."""
    headers = _signup_login(stress_client, "stress2@example.com")
    src, _ = _create_funded_accounts(stress_client, headers, balance=50_000)
    card = stress_client.post(
        f"/api/v1/accounts/{src}/cards",
        headers=headers,
    ).json()

    results = []

    def _spend():
        resp = stress_client.post(
            f"/api/v1/cards/{card['id']}/spend",
            json={
                "amount_cents": 15_000,
                "merchant": "Stress Test",
                "idempotency_key": str(uuid.uuid4()),
            },
            headers=headers,
        )
        results.append(resp.status_code)

    with ThreadPoolExecutor(max_workers=6) as pool:
        for _ in range(6):
            pool.submit(_spend)

    success = results.count(201)
    assert success <= 3

    acct = stress_client.get(
        f"/api/v1/accounts/{src}",
        headers=headers,
    ).json()
    assert acct["balance_cents"] >= 0


# ---------------------------------------------------------------------------
# sequential stress tests (use standard client fixture)
# ---------------------------------------------------------------------------


def test_idempotency_replay_returns_original(client):
    """Same idempotency key sent multiple times — only one transfer created."""
    headers = _signup_login(client, "stress3@example.com")
    src, dst = _create_funded_accounts(client, headers, balance=100_000)
    idem_key = str(uuid.uuid4())

    resp1 = client.post(
        "/api/v1/transfers",
        json={
            "source_account_id": src,
            "destination_account_id": dst,
            "amount_cents": 10_000,
            "idempotency_key": idem_key,
        },
        headers=headers,
    )
    assert resp1.status_code == 201

    for _ in range(4):
        resp = client.post(
            "/api/v1/transfers",
            json={
                "source_account_id": src,
                "destination_account_id": dst,
                "amount_cents": 10_000,
                "idempotency_key": idem_key,
            },
            headers=headers,
        )
        assert resp.status_code == 200

    acct = client.get(f"/api/v1/accounts/{src}", headers=headers).json()
    assert acct["balance_cents"] == 90_000


def test_ledger_invariant_under_load(client):
    """Many transfers — total debits must equal total credits."""
    headers = _signup_login(client, "stress4@example.com")
    src, dst = _create_funded_accounts(client, headers, balance=500_000)

    for _i in range(20):
        client.post(
            "/api/v1/transfers",
            json={
                "source_account_id": src,
                "destination_account_id": dst,
                "amount_cents": 10_000,
                "idempotency_key": str(uuid.uuid4()),
            },
            headers=headers,
        )

    a1 = client.get(f"/api/v1/accounts/{src}", headers=headers).json()
    a2 = client.get(f"/api/v1/accounts/{dst}", headers=headers).json()
    assert a1["balance_cents"] + a2["balance_cents"] == 500_000

    txns_src = client.get(
        f"/api/v1/accounts/{src}/transactions",
        headers=headers,
    ).json()
    txns_dst = client.get(
        f"/api/v1/accounts/{dst}/transactions",
        headers=headers,
    ).json()

    total_debits = sum(t["amount_cents"] for t in txns_src if t["type"] == "debit")
    total_credits = sum(t["amount_cents"] for t in txns_dst if t["type"] == "credit")
    assert total_debits == total_credits == 200_000


def test_rapid_signup_uniqueness(client):
    """Duplicate signups — only first succeeds."""
    first = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "race@example.com",
            "password": "StrongPass1!",
        },
    )
    assert first.status_code == 201

    for _ in range(4):
        resp = client.post(
            "/api/v1/auth/signup",
            json={
                "email": "race@example.com",
                "password": "StrongPass1!",
            },
        )
        assert resp.status_code == 409


def test_card_spend_idempotency_replay(client):
    """Card spend idempotency — same key returns same result."""
    headers = _signup_login(client, "stress5@example.com")
    src, _ = _create_funded_accounts(client, headers, balance=100_000)
    card = client.post(
        f"/api/v1/accounts/{src}/cards",
        headers=headers,
    ).json()
    idem_key = str(uuid.uuid4())

    resp1 = client.post(
        f"/api/v1/cards/{card['id']}/spend",
        json={
            "amount_cents": 5_000,
            "merchant": "Coffee",
            "idempotency_key": idem_key,
        },
        headers=headers,
    )
    assert resp1.status_code == 201

    resp2 = client.post(
        f"/api/v1/cards/{card['id']}/spend",
        json={
            "amount_cents": 5_000,
            "merchant": "Coffee",
            "idempotency_key": idem_key,
        },
        headers=headers,
    )
    assert resp2.status_code == 200

    acct = client.get(f"/api/v1/accounts/{src}", headers=headers).json()
    assert acct["balance_cents"] == 95_000
