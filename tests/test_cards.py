"""TDD tests for cards and card spend transactions."""

import uuid


def _setup_funded_account(client, email="card@example.com"):
    client.post("/api/v1/auth/signup", json={"email": email, "password": "StrongPass1!"})
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass1!"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    client.post(
        "/api/v1/holders",
        json={
            "first_name": "Card",
            "last_name": "User",
            "date_of_birth": "1990-01-01",
        },
        headers=headers,
    )
    acct = client.post(
        "/api/v1/accounts", json={"account_type": "checking"}, headers=headers
    ).json()
    client.post(
        f"/api/v1/accounts/{acct['id']}/deposit", json={"amount_cents": 50000}, headers=headers
    )
    return headers, acct["id"]


# --- Card issuance ---


def test_issue_card(client):
    headers, acct_id = _setup_funded_account(client)
    resp = client.post(f"/api/v1/accounts/{acct_id}/cards", headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "active"
    assert body["account_id"] == acct_id
    assert "card_number" in body
    assert "expiry_date" in body


def test_list_cards(client):
    headers, acct_id = _setup_funded_account(client)
    client.post(f"/api/v1/accounts/{acct_id}/cards", headers=headers)
    client.post(f"/api/v1/accounts/{acct_id}/cards", headers=headers)
    resp = client.get(f"/api/v1/accounts/{acct_id}/cards", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_card(client):
    headers, acct_id = _setup_funded_account(client)
    card = client.post(f"/api/v1/accounts/{acct_id}/cards", headers=headers).json()
    resp = client.get(f"/api/v1/cards/{card['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == card["id"]


# --- Card status updates ---


def test_block_card(client):
    headers, acct_id = _setup_funded_account(client)
    card = client.post(f"/api/v1/accounts/{acct_id}/cards", headers=headers).json()
    resp = client.patch(f"/api/v1/cards/{card['id']}", json={"status": "blocked"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "blocked"


def test_cancel_card(client):
    headers, acct_id = _setup_funded_account(client)
    card = client.post(f"/api/v1/accounts/{acct_id}/cards", headers=headers).json()
    resp = client.patch(
        f"/api/v1/cards/{card['id']}", json={"status": "cancelled"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_invalid_card_status_rejected_by_schema(client):
    headers, acct_id = _setup_funded_account(client)
    card = client.post(f"/api/v1/accounts/{acct_id}/cards", headers=headers).json()
    resp = client.patch(
        f"/api/v1/cards/{card['id']}", json={"status": "suspended"}, headers=headers
    )
    assert resp.status_code == 422


# --- Card spend ---


def test_card_spend_success(client):
    headers, acct_id = _setup_funded_account(client)
    card = client.post(f"/api/v1/accounts/{acct_id}/cards", headers=headers).json()
    resp = client.post(
        f"/api/v1/cards/{card['id']}/spend",
        json={
            "amount_cents": 1500,
            "merchant": "Coffee Shop",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["amount_cents"] == 1500


def test_card_spend_updates_balance(client):
    headers, acct_id = _setup_funded_account(client)
    card = client.post(f"/api/v1/accounts/{acct_id}/cards", headers=headers).json()
    client.post(
        f"/api/v1/cards/{card['id']}/spend",
        json={
            "amount_cents": 2000,
            "merchant": "Grocery",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=headers,
    )
    acct = client.get(f"/api/v1/accounts/{acct_id}", headers=headers).json()
    assert acct["balance_cents"] == 48000  # 50000 - 2000


def test_card_spend_blocked_card(client):
    headers, acct_id = _setup_funded_account(client)
    card = client.post(f"/api/v1/accounts/{acct_id}/cards", headers=headers).json()
    client.patch(f"/api/v1/cards/{card['id']}", json={"status": "blocked"}, headers=headers)
    resp = client.post(
        f"/api/v1/cards/{card['id']}/spend",
        json={
            "amount_cents": 100,
            "merchant": "Test",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert resp.status_code == 400


def test_card_spend_cancelled_card(client):
    headers, acct_id = _setup_funded_account(client)
    card = client.post(f"/api/v1/accounts/{acct_id}/cards", headers=headers).json()
    client.patch(f"/api/v1/cards/{card['id']}", json={"status": "cancelled"}, headers=headers)
    resp = client.post(
        f"/api/v1/cards/{card['id']}/spend",
        json={
            "amount_cents": 100,
            "merchant": "Test",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert resp.status_code == 400


def test_card_spend_frozen_account(client):
    headers, acct_id = _setup_funded_account(client)
    card = client.post(f"/api/v1/accounts/{acct_id}/cards", headers=headers).json()
    client.patch(f"/api/v1/accounts/{acct_id}", json={"status": "frozen"}, headers=headers)
    resp = client.post(
        f"/api/v1/cards/{card['id']}/spend",
        json={
            "amount_cents": 100,
            "merchant": "Test",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert resp.status_code == 400


def test_card_spend_idempotency(client):
    headers, acct_id = _setup_funded_account(client)
    card = client.post(f"/api/v1/accounts/{acct_id}/cards", headers=headers).json()
    key = str(uuid.uuid4())
    r1 = client.post(
        f"/api/v1/cards/{card['id']}/spend",
        json={
            "amount_cents": 500,
            "merchant": "Shop",
            "idempotency_key": key,
        },
        headers=headers,
    )
    r2 = client.post(
        f"/api/v1/cards/{card['id']}/spend",
        json={
            "amount_cents": 500,
            "merchant": "Shop",
            "idempotency_key": key,
        },
        headers=headers,
    )
    assert r1.status_code == 201
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]
    # Balance only debited once
    acct = client.get(f"/api/v1/accounts/{acct_id}", headers=headers).json()
    assert acct["balance_cents"] == 49500


def test_card_spend_cross_user_denied(client):
    headers1, acct_id = _setup_funded_account(client, "card1@example.com")
    card = client.post(f"/api/v1/accounts/{acct_id}/cards", headers=headers1).json()

    client.post(
        "/api/v1/auth/signup", json={"email": "card2@example.com", "password": "StrongPass1!"}
    )
    login2 = client.post(
        "/api/v1/auth/login", json={"email": "card2@example.com", "password": "StrongPass1!"}
    )
    headers2 = {"Authorization": f"Bearer {login2.json()['access_token']}"}

    resp = client.post(
        f"/api/v1/cards/{card['id']}/spend",
        json={
            "amount_cents": 100,
            "merchant": "Test",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=headers2,
    )
    assert resp.status_code == 403
