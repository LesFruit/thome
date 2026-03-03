"""Final comprehensive backend audit — catches every remaining edge case."""

import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _signup(client, email=None, password="testpass123"):  # noqa: S107
    email = email or f"user-{uuid.uuid4().hex[:8]}@test.com"
    r = client.post("/api/v1/auth/signup", json={"email": email, "password": password})
    return r, email


def _login(client, email, password="testpass123"):  # noqa: S107
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def _auth(client, email=None):
    r, email = _signup(client, email)
    tok = _login(client, email).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}, email, tok


def _create_funded_account(client, headers, amount_cents=100_000, acct_type="checking"):
    client.post("/api/v1/holders", json={
        "first_name": "Test", "last_name": "User", "date_of_birth": "1990-01-01",
    }, headers=headers)
    acct = client.post("/api/v1/accounts", json={"account_type": acct_type}, headers=headers).json()
    if amount_cents > 0:
        client.post(f"/api/v1/accounts/{acct['id']}/deposit",
                     json={"amount_cents": amount_cents}, headers=headers)
    return acct


def _idem():
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# 1. Transfer amount edge cases (zero, negative)
# ---------------------------------------------------------------------------
class TestTransferAmountEdgeCases:
    def test_transfer_zero_amount(self, client):
        h, _, _ = _auth(client)
        src = _create_funded_account(client, h, 50_000)
        dst = _create_funded_account(client, h, 0, "savings")
        r = client.post("/api/v1/transfers", json={
            "source_account_id": src["id"], "destination_account_id": dst["id"],
            "amount_cents": 0, "idempotency_key": _idem(),
        }, headers=h)
        assert r.status_code == 400
        assert "positive" in r.json()["error"]["message"].lower()

    def test_transfer_negative_amount(self, client):
        h, _, _ = _auth(client)
        src = _create_funded_account(client, h, 50_000)
        dst = _create_funded_account(client, h, 0, "savings")
        r = client.post("/api/v1/transfers", json={
            "source_account_id": src["id"], "destination_account_id": dst["id"],
            "amount_cents": -5000, "idempotency_key": _idem(),
        }, headers=h)
        assert r.status_code == 400
        assert "positive" in r.json()["error"]["message"].lower()


# ---------------------------------------------------------------------------
# 2. Card spend amount edge cases (zero, negative)
# ---------------------------------------------------------------------------
class TestCardSpendAmountEdgeCases:
    def test_card_spend_zero_amount(self, client):
        h, _, _ = _auth(client)
        acct = _create_funded_account(client, h, 50_000)
        card = client.post(f"/api/v1/accounts/{acct['id']}/cards", headers=h).json()
        r = client.post(f"/api/v1/cards/{card['id']}/spend", json={
            "amount_cents": 0, "merchant": "Shop", "idempotency_key": _idem(),
        }, headers=h)
        assert r.status_code == 400
        assert "positive" in r.json()["error"]["message"].lower()

    def test_card_spend_negative_amount(self, client):
        h, _, _ = _auth(client)
        acct = _create_funded_account(client, h, 50_000)
        card = client.post(f"/api/v1/accounts/{acct['id']}/cards", headers=h).json()
        r = client.post(f"/api/v1/cards/{card['id']}/spend", json={
            "amount_cents": -1000, "merchant": "Shop", "idempotency_key": _idem(),
        }, headers=h)
        assert r.status_code == 400
        assert "positive" in r.json()["error"]["message"].lower()


# ---------------------------------------------------------------------------
# 3. Transfer from closed account
# ---------------------------------------------------------------------------
class TestTransferFromClosedAccount:
    def test_transfer_from_closed_rejected(self, client):
        h, _, _ = _auth(client)
        src = _create_funded_account(client, h, 0)
        dst = _create_funded_account(client, h, 0, "savings")
        # Close source (balance already zero)
        client.patch(f"/api/v1/accounts/{src['id']}", json={"status": "closed"}, headers=h)
        r = client.post("/api/v1/transfers", json={
            "source_account_id": src["id"], "destination_account_id": dst["id"],
            "amount_cents": 100, "idempotency_key": _idem(),
        }, headers=h)
        assert r.status_code == 400
        assert "not active" in r.json()["error"]["message"].lower() or "closed" in r.json()["error"]["message"].lower()


# ---------------------------------------------------------------------------
# 4. Card spend on closed account
# ---------------------------------------------------------------------------
class TestCardSpendOnClosedAccount:
    def test_card_spend_closed_account_rejected(self, client):
        h, _, _ = _auth(client)
        acct = _create_funded_account(client, h, 50_000)
        card = client.post(f"/api/v1/accounts/{acct['id']}/cards", headers=h).json()
        # Drain balance and close
        h2, _, _ = _auth(client)
        dst = _create_funded_account(client, h2, 0)
        client.post("/api/v1/transfers", json={
            "source_account_id": acct["id"], "destination_account_id": dst["id"],
            "amount_cents": 50_000, "idempotency_key": _idem(),
        }, headers=h)
        client.patch(f"/api/v1/accounts/{acct['id']}", json={"status": "closed"}, headers=h)
        r = client.post(f"/api/v1/cards/{card['id']}/spend", json={
            "amount_cents": 100, "merchant": "Shop", "idempotency_key": _idem(),
        }, headers=h)
        assert r.status_code == 400
        assert "closed" in r.json()["error"]["message"].lower()


# ---------------------------------------------------------------------------
# 5. CardUpdateRequest.status — no enum, any string accepted by Pydantic
# ---------------------------------------------------------------------------
class TestCardStatusValidation:
    def test_card_update_invalid_status_string(self, client):
        h, _, _ = _auth(client)
        acct = _create_funded_account(client, h, 50_000)
        card = client.post(f"/api/v1/accounts/{acct['id']}/cards", headers=h).json()
        r = client.patch(f"/api/v1/cards/{card['id']}",
                          json={"status": "invalid_status"}, headers=h)
        # Should be 400 from state machine (not 422 since no schema enum)
        assert r.status_code == 400
        assert "cannot transition" in r.json()["error"]["message"].lower()

    def test_card_active_to_active_rejected(self, client):
        """Same-state transition should fail."""
        h, _, _ = _auth(client)
        acct = _create_funded_account(client, h, 50_000)
        card = client.post(f"/api/v1/accounts/{acct['id']}/cards", headers=h).json()
        assert card["status"] == "active"
        r = client.patch(f"/api/v1/cards/{card['id']}",
                          json={"status": "active"}, headers=h)
        assert r.status_code == 400

    def test_cancelled_card_no_transitions(self, client):
        """Cancelled is terminal — block/active/cancelled all fail."""
        h, _, _ = _auth(client)
        acct = _create_funded_account(client, h, 50_000)
        card = client.post(f"/api/v1/accounts/{acct['id']}/cards", headers=h).json()
        client.patch(f"/api/v1/cards/{card['id']}",
                      json={"status": "cancelled"}, headers=h)
        for target in ["active", "blocked", "cancelled"]:
            r = client.patch(f"/api/v1/cards/{card['id']}",
                              json={"status": target}, headers=h)
            assert r.status_code == 400


# ---------------------------------------------------------------------------
# 6. Transfer list isolation
# ---------------------------------------------------------------------------
class TestTransferListIsolation:
    def test_user_b_cannot_see_user_a_transfers(self, client):
        h_a, _, _ = _auth(client)
        acct_a1 = _create_funded_account(client, h_a, 100_000)
        acct_a2 = _create_funded_account(client, h_a, 0, "savings")
        # A makes a transfer
        client.post("/api/v1/transfers", json={
            "source_account_id": acct_a1["id"], "destination_account_id": acct_a2["id"],
            "amount_cents": 5000, "idempotency_key": _idem(),
        }, headers=h_a)
        # A sees 1 transfer
        r_a = client.get("/api/v1/transfers", headers=h_a)
        assert len(r_a.json()) == 1
        # B sees 0 transfers
        h_b, _, _ = _auth(client)
        _create_funded_account(client, h_b, 0)
        r_b = client.get("/api/v1/transfers", headers=h_b)
        assert len(r_b.json()) == 0

    def test_user_b_cannot_get_user_a_transfer(self, client):
        h_a, _, _ = _auth(client)
        acct_a1 = _create_funded_account(client, h_a, 100_000)
        acct_a2 = _create_funded_account(client, h_a, 0, "savings")
        tr = client.post("/api/v1/transfers", json={
            "source_account_id": acct_a1["id"], "destination_account_id": acct_a2["id"],
            "amount_cents": 5000, "idempotency_key": _idem(),
        }, headers=h_a).json()
        h_b, _, _ = _auth(client)
        _create_funded_account(client, h_b, 0)
        r = client.get(f"/api/v1/transfers/{tr['id']}", headers=h_b)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# 7. Statement list / generate cross-user
# ---------------------------------------------------------------------------
class TestStatementCrossUser:
    def test_list_statements_cross_user_rejected(self, client):
        h_a, _, _ = _auth(client)
        acct_a = _create_funded_account(client, h_a, 50_000)
        h_b, _, _ = _auth(client)
        _create_funded_account(client, h_b, 0)
        r = client.get(f"/api/v1/accounts/{acct_a['id']}/statements", headers=h_b)
        assert r.status_code == 403

    def test_generate_statement_cross_user_rejected(self, client):
        h_a, _, _ = _auth(client)
        acct_a = _create_funded_account(client, h_a, 50_000)
        h_b, _, _ = _auth(client)
        _create_funded_account(client, h_b, 0)
        today = date.today().isoformat()
        r = client.post(f"/api/v1/accounts/{acct_a['id']}/statements", json={
            "start_date": today, "end_date": today,
        }, headers=h_b)
        assert r.status_code == 403

    def test_get_statement_cross_user_rejected(self, client):
        h_a, _, _ = _auth(client)
        acct_a = _create_funded_account(client, h_a, 50_000)
        today = date.today().isoformat()
        stmt = client.post(f"/api/v1/accounts/{acct_a['id']}/statements", json={
            "start_date": today, "end_date": today,
        }, headers=h_a).json()
        h_b, _, _ = _auth(client)
        _create_funded_account(client, h_b, 0)
        r = client.get(f"/api/v1/statements/{stmt['id']}", headers=h_b)
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# 8. Refresh token used as access token
# ---------------------------------------------------------------------------
class TestTokenTypeSeparation:
    def test_refresh_token_as_bearer_rejected(self, client):
        """Refresh token should not work as an access token."""
        _, email = _signup(client)
        tok = _login(client, email).json()
        refresh_as_bearer = {"Authorization": f"Bearer {tok['refresh_token']}"}
        r = client.get("/api/v1/auth/me", headers=refresh_as_bearer)
        assert r.status_code == 401

    def test_access_token_as_refresh_rejected(self, client):
        """Access token should not work as a refresh token."""
        _, email = _signup(client)
        tok = _login(client, email).json()
        r = client.post("/api/v1/auth/refresh", json={
            "refresh_token": tok["access_token"],
        })
        assert r.status_code == 401

    def test_garbage_bearer_token(self, client):
        r = client.get("/api/v1/auth/me",
                        headers={"Authorization": "Bearer not.a.real.jwt.token"})
        assert r.status_code == 401

    def test_empty_bearer_token(self, client):
        r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer "})
        assert r.status_code == 401

    def test_no_auth_header_at_all(self, client):
        r = client.get("/api/v1/auth/me")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# 9. Holder edge cases
# ---------------------------------------------------------------------------
class TestHolderEdgeCases:
    def test_holder_future_dob_accepted(self, client):
        """No min-age guard — future DOB is allowed (design choice)."""
        h, _, _ = _auth(client)
        future = (date.today() + timedelta(days=365)).isoformat()
        r = client.post("/api/v1/holders", json={
            "first_name": "Baby", "last_name": "Future", "date_of_birth": future,
        }, headers=h)
        assert r.status_code == 201

    def test_holder_empty_first_name(self, client):
        """Empty strings pass since no validator — record what happens."""
        h, _, _ = _auth(client)
        r = client.post("/api/v1/holders", json={
            "first_name": "", "last_name": "Test", "date_of_birth": "1990-01-01",
        }, headers=h)
        # No validator blocks it — this should be 201 (design gap, not a bug)
        assert r.status_code == 201
        assert r.json()["first_name"] == ""

    def test_patch_holder_without_holder(self, client):
        h, _, _ = _auth(client)
        r = client.patch("/api/v1/holders/me", json={"first_name": "X"}, headers=h)
        assert r.status_code == 404

    def test_patch_holder_empty_body(self, client):
        """PATCH with no fields should succeed (no-op)."""
        h, _, _ = _auth(client)
        client.post("/api/v1/holders", json={
            "first_name": "A", "last_name": "B", "date_of_birth": "1990-01-01",
        }, headers=h)
        r = client.patch("/api/v1/holders/me", json={}, headers=h)
        assert r.status_code == 200
        assert r.json()["first_name"] == "A"

    def test_holder_invalid_dob_format(self, client):
        h, _, _ = _auth(client)
        r = client.post("/api/v1/holders", json={
            "first_name": "A", "last_name": "B", "date_of_birth": "not-a-date",
        }, headers=h)
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# 10. Account same-status transition
# ---------------------------------------------------------------------------
class TestAccountSameStatusTransition:
    def test_active_to_active_rejected(self, client):
        h, _, _ = _auth(client)
        acct = _create_funded_account(client, h, 0)
        r = client.patch(f"/api/v1/accounts/{acct['id']}",
                          json={"status": "active"}, headers=h)
        assert r.status_code == 400

    def test_frozen_to_frozen_rejected(self, client):
        h, _, _ = _auth(client)
        acct = _create_funded_account(client, h, 0)
        client.patch(f"/api/v1/accounts/{acct['id']}",
                      json={"status": "frozen"}, headers=h)
        r = client.patch(f"/api/v1/accounts/{acct['id']}",
                          json={"status": "frozen"}, headers=h)
        assert r.status_code == 400

    def test_closed_to_closed_rejected(self, client):
        h, _, _ = _auth(client)
        acct = _create_funded_account(client, h, 0)
        client.patch(f"/api/v1/accounts/{acct['id']}",
                      json={"status": "closed"}, headers=h)
        r = client.patch(f"/api/v1/accounts/{acct['id']}",
                          json={"status": "closed"}, headers=h)
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# 11. Card number format + expiry
# ---------------------------------------------------------------------------
class TestCardFormat:
    def test_card_number_starts_with_4_and_is_16_digits(self, client):
        h, _, _ = _auth(client)
        acct = _create_funded_account(client, h, 0)
        card = client.post(f"/api/v1/accounts/{acct['id']}/cards", headers=h).json()
        assert card["card_number"].startswith("4")
        assert len(card["card_number"]) == 16
        assert card["card_number"].isdigit()

    def test_card_expiry_is_in_future(self, client):
        h, _, _ = _auth(client)
        acct = _create_funded_account(client, h, 0)
        card = client.post(f"/api/v1/accounts/{acct['id']}/cards", headers=h).json()
        expiry = date.fromisoformat(card["expiry_date"])
        assert expiry > date.today()


# ---------------------------------------------------------------------------
# 12. Deposit response schema
# ---------------------------------------------------------------------------
class TestDepositResponseSchema:
    def test_deposit_returns_account_response(self, client):
        """Deposit endpoint returns AccountResponse with updated balance."""
        h, _, _ = _auth(client)
        acct = _create_funded_account(client, h, 0)
        r = client.post(f"/api/v1/accounts/{acct['id']}/deposit",
                          json={"amount_cents": 25000}, headers=h)
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == acct["id"]
        assert body["balance_cents"] == 25000
        assert body["status"] == "active"
        assert body["account_type"] in ("checking", "savings")
        assert "created_at" in body
        assert "holder_id" in body

    def test_deposit_transaction_record(self, client):
        h, _, _ = _auth(client)
        acct = _create_funded_account(client, h, 0)
        client.post(f"/api/v1/accounts/{acct['id']}/deposit",
                      json={"amount_cents": 15000}, headers=h)
        txns = client.get(f"/api/v1/accounts/{acct['id']}/transactions", headers=h).json()
        assert len(txns) == 1
        assert txns[0]["type"] == "deposit"
        assert txns[0]["amount_cents"] == 15000
        assert txns[0]["transfer_id"] is None
        assert "Deposit" in txns[0]["description"]


# ---------------------------------------------------------------------------
# 13. Multiple statements for same period
# ---------------------------------------------------------------------------
class TestDuplicateStatements:
    def test_duplicate_statements_allowed(self, client):
        h, _, _ = _auth(client)
        acct = _create_funded_account(client, h, 50_000)
        today = date.today().isoformat()
        s1 = client.post(f"/api/v1/accounts/{acct['id']}/statements", json={
            "start_date": today, "end_date": today,
        }, headers=h)
        s2 = client.post(f"/api/v1/accounts/{acct['id']}/statements", json={
            "start_date": today, "end_date": today,
        }, headers=h)
        assert s1.status_code == 201
        assert s2.status_code == 201
        assert s1.json()["id"] != s2.json()["id"]
        stmts = client.get(f"/api/v1/accounts/{acct['id']}/statements", headers=h).json()
        assert len(stmts) == 2


# ---------------------------------------------------------------------------
# 14. Login edge cases
# ---------------------------------------------------------------------------
class TestLoginEdgeCases:
    def test_login_empty_email(self, client):
        r = client.post("/api/v1/auth/login", json={
            "email": "", "password": "testpass123",
        })
        assert r.status_code == 422

    def test_login_empty_password(self, client):
        _, email = _signup(client)
        r = client.post("/api/v1/auth/login", json={
            "email": email, "password": "",
        })
        assert r.status_code == 401

    def test_login_missing_fields(self, client):
        r = client.post("/api/v1/auth/login", json={})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# 15. Signup edge cases
# ---------------------------------------------------------------------------
class TestSignupEdgeCases:
    def test_signup_missing_email(self, client):
        r = client.post("/api/v1/auth/signup", json={"password": "testpass123"})
        assert r.status_code == 422

    def test_signup_missing_password(self, client):
        r = client.post("/api/v1/auth/signup", json={"email": "a@test.com"})
        assert r.status_code == 422

    def test_signup_password_exactly_7_chars(self, client):
        r = client.post("/api/v1/auth/signup", json={
            "email": f"u-{uuid.uuid4().hex[:6]}@test.com", "password": "1234567",
        })
        assert r.status_code == 422

    def test_signup_invalid_email_format(self, client):
        r = client.post("/api/v1/auth/signup", json={
            "email": "not-an-email", "password": "testpass123",
        })
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# 16. Account type enforcement
# ---------------------------------------------------------------------------
class TestAccountTypeEnforcement:
    def test_savings_account_creation(self, client):
        h, _, _ = _auth(client)
        acct = _create_funded_account(client, h, 0, "savings")
        assert acct["account_type"] == "savings"

    def test_uppercase_account_type_rejected(self, client):
        h, _, _ = _auth(client)
        client.post("/api/v1/holders", json={
            "first_name": "T", "last_name": "U", "date_of_birth": "1990-01-01",
        }, headers=h)
        r = client.post("/api/v1/accounts", json={"account_type": "CHECKING"}, headers=h)
        assert r.status_code == 422

    def test_numeric_account_type_rejected(self, client):
        h, _, _ = _auth(client)
        client.post("/api/v1/holders", json={
            "first_name": "T", "last_name": "U", "date_of_birth": "1990-01-01",
        }, headers=h)
        r = client.post("/api/v1/accounts", json={"account_type": "123"}, headers=h)
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# 17. Cross-user card operations
# ---------------------------------------------------------------------------
class TestCrossUserCardOps:
    def test_issue_card_cross_user_rejected(self, client):
        h_a, _, _ = _auth(client)
        acct_a = _create_funded_account(client, h_a, 50_000)
        h_b, _, _ = _auth(client)
        _create_funded_account(client, h_b, 0)
        r = client.post(f"/api/v1/accounts/{acct_a['id']}/cards", headers=h_b)
        assert r.status_code == 403

    def test_update_card_cross_user_rejected(self, client):
        h_a, _, _ = _auth(client)
        acct_a = _create_funded_account(client, h_a, 50_000)
        card = client.post(f"/api/v1/accounts/{acct_a['id']}/cards", headers=h_a).json()
        h_b, _, _ = _auth(client)
        _create_funded_account(client, h_b, 0)
        r = client.patch(f"/api/v1/cards/{card['id']}",
                          json={"status": "blocked"}, headers=h_b)
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# 18. Transaction list cross-user
# ---------------------------------------------------------------------------
class TestTransactionListCrossUser:
    def test_list_transactions_cross_user_rejected(self, client):
        h_a, _, _ = _auth(client)
        acct_a = _create_funded_account(client, h_a, 50_000)
        h_b, _, _ = _auth(client)
        _create_funded_account(client, h_b, 0)
        r = client.get(f"/api/v1/accounts/{acct_a['id']}/transactions", headers=h_b)
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# 19. Comprehensive ledger math after mixed operations
# ---------------------------------------------------------------------------
class TestComprehensiveLedgerMath:
    def test_ledger_sum_matches_balance_after_all_op_types(self, client):
        """Deposit + transfer out + transfer in + card spend → ledger == balance."""
        h, _, _ = _auth(client)
        acct = _create_funded_account(client, h, 100_000)
        other = _create_funded_account(client, h, 50_000, "savings")
        card = client.post(f"/api/v1/accounts/{acct['id']}/cards", headers=h).json()

        # Transfer out 20000
        client.post("/api/v1/transfers", json={
            "source_account_id": acct["id"], "destination_account_id": other["id"],
            "amount_cents": 20_000, "idempotency_key": _idem(),
        }, headers=h)
        # Transfer in 10000
        client.post("/api/v1/transfers", json={
            "source_account_id": other["id"], "destination_account_id": acct["id"],
            "amount_cents": 10_000, "idempotency_key": _idem(),
        }, headers=h)
        # Card spend 5000
        client.post(f"/api/v1/cards/{card['id']}/spend", json={
            "amount_cents": 5_000, "merchant": "Store", "idempotency_key": _idem(),
        }, headers=h)
        # Another deposit 15000
        client.post(f"/api/v1/accounts/{acct['id']}/deposit",
                      json={"amount_cents": 15_000}, headers=h)

        # Expected: 100000 - 20000 + 10000 - 5000 + 15000 = 100000
        balance = client.get(f"/api/v1/accounts/{acct['id']}", headers=h).json()["balance_cents"]
        assert balance == 100_000

        txns = client.get(f"/api/v1/accounts/{acct['id']}/transactions", headers=h).json()
        ledger = 0
        for t in txns:
            if t["type"] in ("credit", "deposit"):
                ledger += t["amount_cents"]
            elif t["type"] in ("debit", "card_spend"):
                ledger -= t["amount_cents"]
        assert ledger == balance


# ---------------------------------------------------------------------------
# 20. Nonexistent resource IDs
# ---------------------------------------------------------------------------
class TestNonexistentResources:
    def test_get_nonexistent_account(self, client):
        h, _, _ = _auth(client)
        _create_funded_account(client, h, 0)
        r = client.get("/api/v1/accounts/nonexistent-id", headers=h)
        assert r.status_code == 404

    def test_patch_nonexistent_account(self, client):
        h, _, _ = _auth(client)
        _create_funded_account(client, h, 0)
        r = client.patch("/api/v1/accounts/nonexistent-id",
                          json={"status": "frozen"}, headers=h)
        assert r.status_code == 404

    def test_deposit_nonexistent_account(self, client):
        h, _, _ = _auth(client)
        _create_funded_account(client, h, 0)
        r = client.post("/api/v1/accounts/nonexistent-id/deposit",
                          json={"amount_cents": 1000}, headers=h)
        assert r.status_code == 404

    def test_get_nonexistent_transfer(self, client):
        h, _, _ = _auth(client)
        _create_funded_account(client, h, 0)
        r = client.get("/api/v1/transfers/nonexistent-id", headers=h)
        assert r.status_code == 404

    def test_get_nonexistent_statement(self, client):
        h, _, _ = _auth(client)
        _create_funded_account(client, h, 0)
        r = client.get("/api/v1/statements/nonexistent-id", headers=h)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# 21. Health / Ready endpoints
# ---------------------------------------------------------------------------
class TestInfrastructureEndpoints:
    def test_health_has_required_fields(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "healthy"

    def test_ready_has_required_fields(self, client):
        r = client.get("/ready")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ready"

    def test_health_has_response_headers(self, client):
        r = client.get("/health")
        assert "x-request-id" in r.headers
        assert "x-process-time" in r.headers
        assert float(r.headers["x-process-time"]) >= 0


# ---------------------------------------------------------------------------
# 22. Transfer response schema verification
# ---------------------------------------------------------------------------
class TestTransferResponseSchema:
    def test_transfer_response_has_all_fields(self, client):
        h, _, _ = _auth(client)
        src = _create_funded_account(client, h, 100_000)
        dst = _create_funded_account(client, h, 0, "savings")
        r = client.post("/api/v1/transfers", json={
            "source_account_id": src["id"], "destination_account_id": dst["id"],
            "amount_cents": 10_000, "idempotency_key": _idem(),
        }, headers=h)
        assert r.status_code == 201
        body = r.json()
        assert body["source_account_id"] == src["id"]
        assert body["destination_account_id"] == dst["id"]
        assert body["amount_cents"] == 10_000
        assert body["status"] == "completed"
        assert "id" in body
        assert "idempotency_key" in body
        assert "created_at" in body


# ---------------------------------------------------------------------------
# 23. Card spend — whitespace-only merchant variations
# ---------------------------------------------------------------------------
class TestMerchantValidation:
    def test_whitespace_only_merchant_rejected(self, client):
        h, _, _ = _auth(client)
        acct = _create_funded_account(client, h, 50_000)
        card = client.post(f"/api/v1/accounts/{acct['id']}/cards", headers=h).json()
        r = client.post(f"/api/v1/cards/{card['id']}/spend", json={
            "amount_cents": 1000, "merchant": "   ", "idempotency_key": _idem(),
        }, headers=h)
        assert r.status_code == 422

    def test_tabs_and_newlines_merchant_rejected(self, client):
        h, _, _ = _auth(client)
        acct = _create_funded_account(client, h, 50_000)
        card = client.post(f"/api/v1/accounts/{acct['id']}/cards", headers=h).json()
        r = client.post(f"/api/v1/cards/{card['id']}/spend", json={
            "amount_cents": 1000, "merchant": "\t\n", "idempotency_key": _idem(),
        }, headers=h)
        assert r.status_code == 422

    def test_valid_merchant_accepted(self, client):
        h, _, _ = _auth(client)
        acct = _create_funded_account(client, h, 50_000)
        card = client.post(f"/api/v1/accounts/{acct['id']}/cards", headers=h).json()
        r = client.post(f"/api/v1/cards/{card['id']}/spend", json={
            "amount_cents": 1000, "merchant": "Amazon", "idempotency_key": _idem(),
        }, headers=h)
        assert r.status_code == 201


# ---------------------------------------------------------------------------
# 24. Card spend insufficient funds boundary
# ---------------------------------------------------------------------------
class TestCardSpendBoundary:
    def test_spend_exact_balance(self, client):
        h, _, _ = _auth(client)
        acct = _create_funded_account(client, h, 10_000)
        card = client.post(f"/api/v1/accounts/{acct['id']}/cards", headers=h).json()
        r = client.post(f"/api/v1/cards/{card['id']}/spend", json={
            "amount_cents": 10_000, "merchant": "Shop", "idempotency_key": _idem(),
        }, headers=h)
        assert r.status_code == 201
        bal = client.get(f"/api/v1/accounts/{acct['id']}", headers=h).json()["balance_cents"]
        assert bal == 0

    def test_spend_one_over_balance(self, client):
        h, _, _ = _auth(client)
        acct = _create_funded_account(client, h, 10_000)
        card = client.post(f"/api/v1/accounts/{acct['id']}/cards", headers=h).json()
        r = client.post(f"/api/v1/cards/{card['id']}/spend", json={
            "amount_cents": 10_001, "merchant": "Shop", "idempotency_key": _idem(),
        }, headers=h)
        assert r.status_code == 400
        assert "insufficient" in r.json()["error"]["message"].lower()


# ---------------------------------------------------------------------------
# 25. Full lifecycle — signup to close
# ---------------------------------------------------------------------------
class TestFullLifecycle:
    def test_complete_user_journey(self, client):
        """End-to-end: signup → holder → account → deposit → transfer →
        card → spend → statement → freeze → unfreeze → drain → close."""
        # Signup + login
        r, email = _signup(client)
        assert r.status_code == 201
        tok = _login(client, email).json()
        h = {"Authorization": f"Bearer {tok['access_token']}"}

        # Me
        me = client.get("/api/v1/auth/me", headers=h).json()
        assert me["email"] == email

        # Holder
        client.post("/api/v1/holders", json={
            "first_name": "Lifecycle", "last_name": "Test", "date_of_birth": "1985-06-15",
        }, headers=h)

        # Two accounts
        acct1 = client.post("/api/v1/accounts",
                             json={"account_type": "checking"}, headers=h).json()
        acct2 = client.post("/api/v1/accounts",
                             json={"account_type": "savings"}, headers=h).json()

        # Deposit
        client.post(f"/api/v1/accounts/{acct1['id']}/deposit",
                      json={"amount_cents": 200_000}, headers=h)

        # Transfer
        client.post("/api/v1/transfers", json={
            "source_account_id": acct1["id"], "destination_account_id": acct2["id"],
            "amount_cents": 50_000, "idempotency_key": _idem(),
        }, headers=h)

        # Card
        card = client.post(f"/api/v1/accounts/{acct1['id']}/cards", headers=h).json()
        client.post(f"/api/v1/cards/{card['id']}/spend", json={
            "amount_cents": 10_000, "merchant": "Coffee", "idempotency_key": _idem(),
        }, headers=h)

        # Statement
        today = date.today().isoformat()
        stmt = client.post(f"/api/v1/accounts/{acct1['id']}/statements", json={
            "start_date": today, "end_date": today,
        }, headers=h).json()
        assert stmt["transaction_count"] >= 3

        # Freeze, unfreeze
        client.patch(f"/api/v1/accounts/{acct1['id']}",
                      json={"status": "frozen"}, headers=h)
        client.patch(f"/api/v1/accounts/{acct1['id']}",
                      json={"status": "active"}, headers=h)

        # Drain to savings and close checking
        bal = client.get(f"/api/v1/accounts/{acct1['id']}", headers=h).json()["balance_cents"]
        if bal > 0:
            client.post("/api/v1/transfers", json={
                "source_account_id": acct1["id"], "destination_account_id": acct2["id"],
                "amount_cents": bal, "idempotency_key": _idem(),
            }, headers=h)
        r = client.patch(f"/api/v1/accounts/{acct1['id']}",
                          json={"status": "closed"}, headers=h)
        assert r.status_code == 200
        assert r.json()["status"] == "closed"

        # Logout
        r = client.post("/api/v1/auth/logout", json={
            "refresh_token": tok["refresh_token"],
        }, headers=h)
        assert r.status_code == 200
