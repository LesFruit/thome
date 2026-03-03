"""TDD tests for transfers and transactions — double-entry ledger, idempotency, atomic overdraft."""

import uuid


def _setup_two_accounts(client):
    """Create a user with two accounts, fund the first with 10000 cents ($100)."""
    client.post("/api/v1/auth/signup", json={"email": "xfer@example.com", "password": "StrongPass1!"})
    login = client.post("/api/v1/auth/login", json={"email": "xfer@example.com", "password": "StrongPass1!"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/api/v1/holders", json={
        "first_name": "Jane", "last_name": "Doe", "date_of_birth": "1990-01-01",
    }, headers=headers)

    a1 = client.post("/api/v1/accounts", json={"account_type": "checking"}, headers=headers).json()
    a2 = client.post("/api/v1/accounts", json={"account_type": "savings"}, headers=headers).json()

    # Seed balance via internal endpoint
    client.post(f"/api/v1/accounts/{a1['id']}/deposit", json={"amount_cents": 10000}, headers=headers)

    return headers, a1["id"], a2["id"]


# --- Transfer creation ---

def test_transfer_success(client):
    headers, src, dst = _setup_two_accounts(client)
    resp = client.post("/api/v1/transfers", json={
        "source_account_id": src,
        "destination_account_id": dst,
        "amount_cents": 5000,
        "idempotency_key": str(uuid.uuid4()),
    }, headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["amount_cents"] == 5000
    assert body["status"] == "completed"


def test_transfer_updates_balances(client):
    headers, src, dst = _setup_two_accounts(client)
    client.post("/api/v1/transfers", json={
        "source_account_id": src,
        "destination_account_id": dst,
        "amount_cents": 3000,
        "idempotency_key": str(uuid.uuid4()),
    }, headers=headers)

    src_acct = client.get(f"/api/v1/accounts/{src}", headers=headers).json()
    dst_acct = client.get(f"/api/v1/accounts/{dst}", headers=headers).json()
    assert src_acct["balance_cents"] == 7000  # 10000 - 3000
    assert dst_acct["balance_cents"] == 3000


def test_transfer_creates_double_entry(client):
    headers, src, dst = _setup_two_accounts(client)
    client.post("/api/v1/transfers", json={
        "source_account_id": src,
        "destination_account_id": dst,
        "amount_cents": 2000,
        "idempotency_key": str(uuid.uuid4()),
    }, headers=headers)

    # Check transactions for source account
    txns = client.get(f"/api/v1/accounts/{src}/transactions", headers=headers).json()
    debit = [t for t in txns if t["type"] == "debit"]
    assert len(debit) >= 1
    assert debit[0]["amount_cents"] == 2000

    # Check transactions for destination
    txns = client.get(f"/api/v1/accounts/{dst}/transactions", headers=headers).json()
    credit = [t for t in txns if t["type"] == "credit"]
    assert len(credit) >= 1
    assert credit[0]["amount_cents"] == 2000


# --- Overdraft prevention ---

def test_transfer_insufficient_funds(client):
    headers, src, dst = _setup_two_accounts(client)
    resp = client.post("/api/v1/transfers", json={
        "source_account_id": src,
        "destination_account_id": dst,
        "amount_cents": 99999,
        "idempotency_key": str(uuid.uuid4()),
    }, headers=headers)
    assert resp.status_code == 400


# --- Self-transfer ---

def test_self_transfer_rejected(client):
    headers, src, _ = _setup_two_accounts(client)
    resp = client.post("/api/v1/transfers", json={
        "source_account_id": src,
        "destination_account_id": src,
        "amount_cents": 100,
        "idempotency_key": str(uuid.uuid4()),
    }, headers=headers)
    assert resp.status_code == 400


# --- Idempotency ---

def test_idempotency_key_replay(client):
    headers, src, dst = _setup_two_accounts(client)
    key = str(uuid.uuid4())
    r1 = client.post("/api/v1/transfers", json={
        "source_account_id": src,
        "destination_account_id": dst,
        "amount_cents": 1000,
        "idempotency_key": key,
    }, headers=headers)
    r2 = client.post("/api/v1/transfers", json={
        "source_account_id": src,
        "destination_account_id": dst,
        "amount_cents": 1000,
        "idempotency_key": key,
    }, headers=headers)
    assert r1.status_code == 201
    assert r2.status_code == 200  # replayed, not re-created
    assert r1.json()["id"] == r2.json()["id"]

    # Balance only debited once
    src_acct = client.get(f"/api/v1/accounts/{src}", headers=headers).json()
    assert src_acct["balance_cents"] == 9000  # 10000 - 1000 (not 8000)


# --- Listing ---

def test_list_transfers(client):
    headers, src, dst = _setup_two_accounts(client)
    for i in range(3):
        client.post("/api/v1/transfers", json={
            "source_account_id": src,
            "destination_account_id": dst,
            "amount_cents": 100,
            "idempotency_key": str(uuid.uuid4()),
        }, headers=headers)

    resp = client.get("/api/v1/transfers", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 3


def test_get_transfer(client):
    headers, src, dst = _setup_two_accounts(client)
    create = client.post("/api/v1/transfers", json={
        "source_account_id": src,
        "destination_account_id": dst,
        "amount_cents": 500,
        "idempotency_key": str(uuid.uuid4()),
    }, headers=headers)
    xfer_id = create.json()["id"]
    resp = client.get(f"/api/v1/transfers/{xfer_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == xfer_id


# --- Cross-user access ---

def test_cross_user_transfer_denied(client):
    # Setup first user
    headers1, src, dst = _setup_two_accounts(client)

    # Setup second user
    client.post("/api/v1/auth/signup", json={"email": "other@example.com", "password": "StrongPass1!"})
    login2 = client.post("/api/v1/auth/login", json={"email": "other@example.com", "password": "StrongPass1!"})
    headers2 = {"Authorization": f"Bearer {login2.json()['access_token']}"}

    resp = client.post("/api/v1/transfers", json={
        "source_account_id": src,
        "destination_account_id": dst,
        "amount_cents": 100,
        "idempotency_key": str(uuid.uuid4()),
    }, headers=headers2)
    assert resp.status_code == 403
