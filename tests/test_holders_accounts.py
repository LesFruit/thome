"""TDD tests for account holders and accounts."""

import pytest


def _signup_and_login(client, email="holder@example.com"):
    client.post("/api/v1/auth/signup", json={"email": email, "password": "StrongPass1!"})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass1!"})
    return resp.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# --- Account Holders ---

def test_create_holder(client):
    token = _signup_and_login(client)
    resp = client.post("/api/v1/holders", json={
        "first_name": "John",
        "last_name": "Doe",
        "date_of_birth": "1990-01-15",
    }, headers=_auth(token))
    assert resp.status_code == 201
    body = resp.json()
    assert body["first_name"] == "John"
    assert body["last_name"] == "Doe"
    assert "id" in body


def test_create_holder_requires_auth(client):
    resp = client.post("/api/v1/holders", json={
        "first_name": "John",
        "last_name": "Doe",
        "date_of_birth": "1990-01-15",
    })
    assert resp.status_code == 401


def test_duplicate_holder_rejected(client):
    token = _signup_and_login(client)
    client.post("/api/v1/holders", json={
        "first_name": "John",
        "last_name": "Doe",
        "date_of_birth": "1990-01-15",
    }, headers=_auth(token))
    resp = client.post("/api/v1/holders", json={
        "first_name": "Jane",
        "last_name": "Doe",
        "date_of_birth": "1992-03-20",
    }, headers=_auth(token))
    assert resp.status_code == 409


def test_get_holder(client):
    token = _signup_and_login(client)
    client.post("/api/v1/holders", json={
        "first_name": "John",
        "last_name": "Doe",
        "date_of_birth": "1990-01-15",
    }, headers=_auth(token))
    resp = client.get("/api/v1/holders/me", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["first_name"] == "John"


def test_get_holder_not_found(client):
    token = _signup_and_login(client)
    resp = client.get("/api/v1/holders/me", headers=_auth(token))
    assert resp.status_code == 404


def test_update_holder(client):
    token = _signup_and_login(client)
    client.post("/api/v1/holders", json={
        "first_name": "John",
        "last_name": "Doe",
        "date_of_birth": "1990-01-15",
    }, headers=_auth(token))
    resp = client.patch("/api/v1/holders/me", json={
        "last_name": "Smith",
    }, headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["last_name"] == "Smith"


# --- Accounts ---

def test_create_account(client):
    token = _signup_and_login(client)
    client.post("/api/v1/holders", json={
        "first_name": "John",
        "last_name": "Doe",
        "date_of_birth": "1990-01-15",
    }, headers=_auth(token))
    resp = client.post("/api/v1/accounts", json={
        "account_type": "checking",
    }, headers=_auth(token))
    assert resp.status_code == 201
    body = resp.json()
    assert body["account_type"] == "checking"
    assert body["status"] == "active"
    assert body["balance_cents"] == 0


def test_create_account_requires_holder(client):
    token = _signup_and_login(client)
    resp = client.post("/api/v1/accounts", json={
        "account_type": "checking",
    }, headers=_auth(token))
    assert resp.status_code == 400


def test_list_accounts(client):
    token = _signup_and_login(client)
    client.post("/api/v1/holders", json={
        "first_name": "John",
        "last_name": "Doe",
        "date_of_birth": "1990-01-15",
    }, headers=_auth(token))
    client.post("/api/v1/accounts", json={"account_type": "checking"}, headers=_auth(token))
    client.post("/api/v1/accounts", json={"account_type": "savings"}, headers=_auth(token))
    resp = client.get("/api/v1/accounts", headers=_auth(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_account(client):
    token = _signup_and_login(client)
    client.post("/api/v1/holders", json={
        "first_name": "John",
        "last_name": "Doe",
        "date_of_birth": "1990-01-15",
    }, headers=_auth(token))
    create = client.post("/api/v1/accounts", json={"account_type": "checking"}, headers=_auth(token))
    acct_id = create.json()["id"]
    resp = client.get(f"/api/v1/accounts/{acct_id}", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["id"] == acct_id


def test_cross_user_account_access_denied(client):
    token1 = _signup_and_login(client, "user1@example.com")
    token2 = _signup_and_login(client, "user2@example.com")
    client.post("/api/v1/holders", json={
        "first_name": "User",
        "last_name": "One",
        "date_of_birth": "1990-01-15",
    }, headers=_auth(token1))
    create = client.post("/api/v1/accounts", json={"account_type": "checking"}, headers=_auth(token1))
    acct_id = create.json()["id"]
    resp = client.get(f"/api/v1/accounts/{acct_id}", headers=_auth(token2))
    assert resp.status_code == 403


def test_freeze_account(client):
    token = _signup_and_login(client)
    client.post("/api/v1/holders", json={
        "first_name": "John",
        "last_name": "Doe",
        "date_of_birth": "1990-01-15",
    }, headers=_auth(token))
    create = client.post("/api/v1/accounts", json={"account_type": "checking"}, headers=_auth(token))
    acct_id = create.json()["id"]
    resp = client.patch(f"/api/v1/accounts/{acct_id}", json={"status": "frozen"}, headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "frozen"


def test_invalid_status_transition(client):
    token = _signup_and_login(client)
    client.post("/api/v1/holders", json={
        "first_name": "John",
        "last_name": "Doe",
        "date_of_birth": "1990-01-15",
    }, headers=_auth(token))
    create = client.post("/api/v1/accounts", json={"account_type": "checking"}, headers=_auth(token))
    acct_id = create.json()["id"]
    # Close the account
    client.patch(f"/api/v1/accounts/{acct_id}", json={"status": "closed"}, headers=_auth(token))
    # Cannot reactivate a closed account
    resp = client.patch(f"/api/v1/accounts/{acct_id}", json={"status": "active"}, headers=_auth(token))
    assert resp.status_code == 400
