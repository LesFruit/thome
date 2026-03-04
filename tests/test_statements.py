"""TDD tests for statement generation."""

import uuid
from datetime import date


def _setup_account_with_transactions(client):
    """Create a funded account with some transfers for statement data."""
    client.post(
        "/api/v1/auth/signup", json={"email": "stmt@example.com", "password": "StrongPass1!"}
    )
    login = client.post(
        "/api/v1/auth/login", json={"email": "stmt@example.com", "password": "StrongPass1!"}
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    client.post(
        "/api/v1/holders",
        json={
            "first_name": "Stmt",
            "last_name": "User",
            "date_of_birth": "1990-01-01",
        },
        headers=headers,
    )

    a1 = client.post("/api/v1/accounts", json={"account_type": "checking"}, headers=headers).json()
    a2 = client.post("/api/v1/accounts", json={"account_type": "savings"}, headers=headers).json()

    # Fund a1 with 100000 cents ($1000)
    client.post(
        f"/api/v1/accounts/{a1['id']}/deposit", json={"amount_cents": 100000}, headers=headers
    )

    # Make a few transfers
    for amt in [5000, 3000, 2000]:
        client.post(
            "/api/v1/transfers",
            json={
                "source_account_id": a1["id"],
                "destination_account_id": a2["id"],
                "amount_cents": amt,
                "idempotency_key": str(uuid.uuid4()),
            },
            headers=headers,
        )

    return headers, a1["id"], a2["id"]


def test_generate_statement(client):
    headers, acct_id, _ = _setup_account_with_transactions(client)
    today = date.today().isoformat()
    resp = client.post(
        f"/api/v1/accounts/{acct_id}/statements",
        json={
            "start_date": "2020-01-01",
            "end_date": today,
        },
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body
    assert body["account_id"] == acct_id
    assert body["total_debits_cents"] == 10000  # 5000 + 3000 + 2000
    assert body["total_credits_cents"] == 100000  # deposit
    assert body["transaction_count"] >= 4  # 1 deposit + 3 debits


def test_statement_balances(client):
    headers, acct_id, _ = _setup_account_with_transactions(client)
    today = date.today().isoformat()
    resp = client.post(
        f"/api/v1/accounts/{acct_id}/statements",
        json={
            "start_date": "2020-01-01",
            "end_date": today,
        },
        headers=headers,
    )
    body = resp.json()
    # opening_balance = 0 (before any transactions)
    assert body["opening_balance_cents"] == 0
    # closing = opening + credits - debits = 0 + 100000 - 10000 = 90000
    assert body["closing_balance_cents"] == 90000


def test_list_statements(client):
    headers, acct_id, _ = _setup_account_with_transactions(client)
    today = date.today().isoformat()
    # Generate two statements
    client.post(
        f"/api/v1/accounts/{acct_id}/statements",
        json={
            "start_date": "2020-01-01",
            "end_date": today,
        },
        headers=headers,
    )
    client.post(
        f"/api/v1/accounts/{acct_id}/statements",
        json={
            "start_date": "2020-06-01",
            "end_date": today,
        },
        headers=headers,
    )
    resp = client.get(f"/api/v1/accounts/{acct_id}/statements", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_duplicate_statement_same_period_rejected(client):
    headers, acct_id, _ = _setup_account_with_transactions(client)
    today = date.today().isoformat()
    first = client.post(
        f"/api/v1/accounts/{acct_id}/statements",
        json={
            "start_date": "2020-01-01",
            "end_date": today,
        },
        headers=headers,
    )
    duplicate = client.post(
        f"/api/v1/accounts/{acct_id}/statements",
        json={
            "start_date": "2020-01-01",
            "end_date": today,
        },
        headers=headers,
    )
    assert first.status_code == 201
    assert duplicate.status_code == 409


def test_get_statement(client):
    headers, acct_id, _ = _setup_account_with_transactions(client)
    today = date.today().isoformat()
    create = client.post(
        f"/api/v1/accounts/{acct_id}/statements",
        json={
            "start_date": "2020-01-01",
            "end_date": today,
        },
        headers=headers,
    )
    stmt_id = create.json()["id"]
    resp = client.get(f"/api/v1/statements/{stmt_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == stmt_id


def test_statement_unauthorized_access(client):
    headers1, acct_id, _ = _setup_account_with_transactions(client)
    today = date.today().isoformat()
    create = client.post(
        f"/api/v1/accounts/{acct_id}/statements",
        json={
            "start_date": "2020-01-01",
            "end_date": today,
        },
        headers=headers1,
    )
    stmt_id = create.json()["id"]

    # Second user
    client.post(
        "/api/v1/auth/signup", json={"email": "other@example.com", "password": "StrongPass1!"}
    )
    login2 = client.post(
        "/api/v1/auth/login", json={"email": "other@example.com", "password": "StrongPass1!"}
    )
    headers2 = {"Authorization": f"Bearer {login2.json()['access_token']}"}

    resp = client.get(f"/api/v1/statements/{stmt_id}", headers=headers2)
    assert resp.status_code == 403
