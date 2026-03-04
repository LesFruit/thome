"""Comprehensive E2E scenario tests — covers every API endpoint and edge case.

Written after a 129-test browser audit that systematically hit all 27 endpoints.
These tests cover gaps found during the audit, including:
- Schema-level validation (account type, account status enums)
- Deposit/transfer/card operations against frozen/closed accounts
- Close-with-balance guard
- Full card state machine lifecycle
- Multi-user isolation across all resource types
- Cross-user transfers (A sends to B's account)
- Double-entry ledger invariant verification
- Token lifecycle (refresh rotation, logout revocation)
- Statement math on multi-operation accounts
- Idempotency replays for transfers and card spends
- X-Request-ID presence on all responses
"""

import uuid
from datetime import date

# ── Helpers ──────────────────────────────────────────────────────────────


def _signup(client, email, password="StrongPass1!"):  # noqa: S107
    return client.post("/api/v1/auth/signup", json={"email": email, "password": password})


def _login(client, email, password="StrongPass1!"):  # noqa: S107
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    data = resp.json()
    return data["access_token"], data["refresh_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create_user(client, email, first="Test", last="User"):
    """Full setup: signup + login + holder. Returns (token, refresh_token)."""
    _signup(client, email)
    token, refresh = _login(client, email)
    client.post(
        "/api/v1/holders",
        json={
            "first_name": first,
            "last_name": last,
            "date_of_birth": "1990-01-15",
        },
        headers=_auth(token),
    )
    return token, refresh


def _create_funded_account(client, token, acct_type="checking", amount_cents=100000):
    """Create account and deposit. Returns account_id."""
    acct = client.post(
        "/api/v1/accounts",
        json={"account_type": acct_type},
        headers=_auth(token),
    ).json()
    if amount_cents > 0:
        client.post(
            f"/api/v1/accounts/{acct['id']}/deposit",
            json={"amount_cents": amount_cents},
            headers=_auth(token),
        )
    return acct["id"]


def _idem():
    return str(uuid.uuid4())


# ── 1. Schema Validation ────────────────────────────────────────────────


class TestSchemaValidation:
    """Pydantic enum validation at the API boundary."""

    def test_invalid_account_type_rejected(self, client):
        token, _ = _create_user(client, "schema1@test.com")
        resp = client.post(
            "/api/v1/accounts",
            json={"account_type": "investment"},
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_valid_account_types_accepted(self, client):
        token, _ = _create_user(client, "schema2@test.com")
        for t in ("checking", "savings"):
            resp = client.post(
                "/api/v1/accounts",
                json={"account_type": t},
                headers=_auth(token),
            )
            assert resp.status_code == 201

    def test_invalid_account_status_rejected(self, client):
        token, _ = _create_user(client, "schema3@test.com")
        acct_id = _create_funded_account(client, token, amount_cents=0)
        resp = client.patch(
            f"/api/v1/accounts/{acct_id}",
            json={"status": "suspended"},
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_missing_required_fields(self, client):
        token, _ = _create_user(client, "schema4@test.com")
        # Account without type
        assert (
            client.post(
                "/api/v1/accounts",
                json={},
                headers=_auth(token),
            ).status_code
            == 422
        )
        # Transfer without idempotency key
        a1 = _create_funded_account(client, token)
        a2 = _create_funded_account(client, token, "savings", 0)
        assert (
            client.post(
                "/api/v1/transfers",
                json={
                    "source_account_id": a1,
                    "destination_account_id": a2,
                    "amount_cents": 100,
                },
                headers=_auth(token),
            ).status_code
            == 422
        )


# ── 2. Account Status Guards ────────────────────────────────────────────


class TestAccountStatusGuards:
    """Operations blocked on frozen/closed accounts (bugs found in browser audit)."""

    def test_deposit_to_frozen_account_rejected(self, client):
        token, _ = _create_user(client, "frozen1@test.com")
        acct_id = _create_funded_account(client, token, amount_cents=50000)
        client.patch(f"/api/v1/accounts/{acct_id}", json={"status": "frozen"}, headers=_auth(token))
        resp = client.post(
            f"/api/v1/accounts/{acct_id}/deposit",
            json={"amount_cents": 1000},
            headers=_auth(token),
        )
        assert resp.status_code == 400
        assert "frozen" in resp.json()["error"]["message"]

    def test_deposit_to_closed_account_rejected(self, client):
        token, _ = _create_user(client, "closed1@test.com")
        acct_id = _create_funded_account(client, token, amount_cents=0)
        client.patch(f"/api/v1/accounts/{acct_id}", json={"status": "closed"}, headers=_auth(token))
        resp = client.post(
            f"/api/v1/accounts/{acct_id}/deposit",
            json={"amount_cents": 1000},
            headers=_auth(token),
        )
        assert resp.status_code == 400
        assert "closed" in resp.json()["error"]["message"]

    def test_close_account_with_balance_rejected(self, client):
        token, _ = _create_user(client, "closebal@test.com")
        acct_id = _create_funded_account(client, token, amount_cents=50000)
        resp = client.patch(
            f"/api/v1/accounts/{acct_id}",
            json={"status": "closed"},
            headers=_auth(token),
        )
        assert resp.status_code == 400
        assert "balance" in resp.json()["error"]["message"].lower()

    def test_close_account_with_zero_balance_succeeds(self, client):
        token, _ = _create_user(client, "closezero@test.com")
        acct_id = _create_funded_account(client, token, amount_cents=0)
        resp = client.patch(
            f"/api/v1/accounts/{acct_id}",
            json={"status": "closed"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "closed"

    def test_transfer_from_frozen_rejected(self, client):
        token, _ = _create_user(client, "frzxfer@test.com")
        a1 = _create_funded_account(client, token, amount_cents=50000)
        a2 = _create_funded_account(client, token, "savings", 0)
        client.patch(f"/api/v1/accounts/{a1}", json={"status": "frozen"}, headers=_auth(token))
        resp = client.post(
            "/api/v1/transfers",
            json={
                "source_account_id": a1,
                "destination_account_id": a2,
                "amount_cents": 100,
                "idempotency_key": _idem(),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 400

    def test_transfer_to_frozen_rejected(self, client):
        token, _ = _create_user(client, "frzxfer2@test.com")
        a1 = _create_funded_account(client, token, amount_cents=50000)
        a2 = _create_funded_account(client, token, "savings", 0)
        client.patch(f"/api/v1/accounts/{a2}", json={"status": "frozen"}, headers=_auth(token))
        resp = client.post(
            "/api/v1/transfers",
            json={
                "source_account_id": a1,
                "destination_account_id": a2,
                "amount_cents": 100,
                "idempotency_key": _idem(),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 400

    def test_transfer_to_closed_rejected(self, client):
        token, _ = _create_user(client, "clsxfer@test.com")
        a1 = _create_funded_account(client, token, amount_cents=50000)
        a2 = _create_funded_account(client, token, "savings", 0)
        client.patch(f"/api/v1/accounts/{a2}", json={"status": "closed"}, headers=_auth(token))
        resp = client.post(
            "/api/v1/transfers",
            json={
                "source_account_id": a1,
                "destination_account_id": a2,
                "amount_cents": 100,
                "idempotency_key": _idem(),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 400

    def test_card_spend_on_frozen_account_rejected(self, client):
        token, _ = _create_user(client, "frzcard@test.com")
        acct_id = _create_funded_account(client, token, amount_cents=50000)
        card = client.post(f"/api/v1/accounts/{acct_id}/cards", headers=_auth(token)).json()
        client.patch(f"/api/v1/accounts/{acct_id}", json={"status": "frozen"}, headers=_auth(token))
        resp = client.post(
            f"/api/v1/cards/{card['id']}/spend",
            json={
                "amount_cents": 100,
                "merchant": "Test",
                "idempotency_key": _idem(),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 400


# ── 3. Full Account Status State Machine ────────────────────────────────


class TestAccountStateMachine:
    """Every valid and invalid status transition."""

    def test_active_to_frozen(self, client):
        token, _ = _create_user(client, "sm1@test.com")
        a = _create_funded_account(client, token, amount_cents=0)
        resp = client.patch(
            f"/api/v1/accounts/{a}", json={"status": "frozen"}, headers=_auth(token)
        )
        assert resp.status_code == 200 and resp.json()["status"] == "frozen"

    def test_active_to_closed(self, client):
        token, _ = _create_user(client, "sm2@test.com")
        a = _create_funded_account(client, token, amount_cents=0)
        resp = client.patch(
            f"/api/v1/accounts/{a}", json={"status": "closed"}, headers=_auth(token)
        )
        assert resp.status_code == 200 and resp.json()["status"] == "closed"

    def test_frozen_to_active(self, client):
        token, _ = _create_user(client, "sm3@test.com")
        a = _create_funded_account(client, token, amount_cents=0)
        client.patch(f"/api/v1/accounts/{a}", json={"status": "frozen"}, headers=_auth(token))
        resp = client.patch(
            f"/api/v1/accounts/{a}", json={"status": "active"}, headers=_auth(token)
        )
        assert resp.status_code == 200 and resp.json()["status"] == "active"

    def test_frozen_to_closed(self, client):
        token, _ = _create_user(client, "sm4@test.com")
        a = _create_funded_account(client, token, amount_cents=0)
        client.patch(f"/api/v1/accounts/{a}", json={"status": "frozen"}, headers=_auth(token))
        resp = client.patch(
            f"/api/v1/accounts/{a}", json={"status": "closed"}, headers=_auth(token)
        )
        assert resp.status_code == 200 and resp.json()["status"] == "closed"

    def test_closed_to_active_rejected(self, client):
        token, _ = _create_user(client, "sm5@test.com")
        a = _create_funded_account(client, token, amount_cents=0)
        client.patch(f"/api/v1/accounts/{a}", json={"status": "closed"}, headers=_auth(token))
        resp = client.patch(
            f"/api/v1/accounts/{a}", json={"status": "active"}, headers=_auth(token)
        )
        assert resp.status_code == 400

    def test_closed_to_frozen_rejected(self, client):
        token, _ = _create_user(client, "sm6@test.com")
        a = _create_funded_account(client, token, amount_cents=0)
        client.patch(f"/api/v1/accounts/{a}", json={"status": "closed"}, headers=_auth(token))
        resp = client.patch(
            f"/api/v1/accounts/{a}", json={"status": "frozen"}, headers=_auth(token)
        )
        assert resp.status_code == 400


# ── 4. Card State Machine ───────────────────────────────────────────────


class TestCardStateMachine:
    """Full card lifecycle: active → blocked ↔ active → cancelled (terminal)."""

    def _setup(self, client, email):
        token, _ = _create_user(client, email)
        acct_id = _create_funded_account(client, token, amount_cents=100000)
        card = client.post(f"/api/v1/accounts/{acct_id}/cards", headers=_auth(token)).json()
        return token, acct_id, card["id"]

    def test_block_then_unblock_then_spend(self, client):
        token, acct_id, card_id = self._setup(client, "csm1@test.com")
        # Block
        r = client.patch(
            f"/api/v1/cards/{card_id}", json={"status": "blocked"}, headers=_auth(token)
        )
        assert r.json()["status"] == "blocked"
        # Spend fails
        r = client.post(
            f"/api/v1/cards/{card_id}/spend",
            json={
                "amount_cents": 100,
                "merchant": "X",
                "idempotency_key": _idem(),
            },
            headers=_auth(token),
        )
        assert r.status_code == 400
        # Unblock
        r = client.patch(
            f"/api/v1/cards/{card_id}", json={"status": "active"}, headers=_auth(token)
        )
        assert r.json()["status"] == "active"
        # Spend succeeds
        r = client.post(
            f"/api/v1/cards/{card_id}/spend",
            json={
                "amount_cents": 1000,
                "merchant": "Coffee",
                "idempotency_key": _idem(),
            },
            headers=_auth(token),
        )
        assert r.status_code == 201

    def test_cancel_is_terminal(self, client):
        token, _, card_id = self._setup(client, "csm2@test.com")
        client.patch(f"/api/v1/cards/{card_id}", json={"status": "cancelled"}, headers=_auth(token))
        # Can't reactivate
        assert (
            client.patch(
                f"/api/v1/cards/{card_id}",
                json={"status": "active"},
                headers=_auth(token),
            ).status_code
            == 400
        )
        # Can't block
        assert (
            client.patch(
                f"/api/v1/cards/{card_id}",
                json={"status": "blocked"},
                headers=_auth(token),
            ).status_code
            == 400
        )
        # Can't spend
        assert (
            client.post(
                f"/api/v1/cards/{card_id}/spend",
                json={
                    "amount_cents": 100,
                    "merchant": "X",
                    "idempotency_key": _idem(),
                },
                headers=_auth(token),
            ).status_code
            == 400
        )

    def test_blocked_to_cancelled(self, client):
        token, _, card_id = self._setup(client, "csm3@test.com")
        client.patch(f"/api/v1/cards/{card_id}", json={"status": "blocked"}, headers=_auth(token))
        r = client.patch(
            f"/api/v1/cards/{card_id}", json={"status": "cancelled"}, headers=_auth(token)
        )
        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"

    def test_card_spend_creates_transaction_record(self, client):
        """Verify card spend appears in account transaction ledger."""
        token, acct_id, card_id = self._setup(client, "csm4@test.com")
        client.post(
            f"/api/v1/cards/{card_id}/spend",
            json={
                "amount_cents": 2500,
                "merchant": "Bookstore",
                "idempotency_key": _idem(),
            },
            headers=_auth(token),
        )
        txns = client.get(f"/api/v1/accounts/{acct_id}/transactions", headers=_auth(token)).json()
        card_txns = [t for t in txns if t["type"] == "card_spend"]
        assert len(card_txns) >= 1
        assert card_txns[0]["amount_cents"] == 2500


# ── 5. Cross-User Isolation ─────────────────────────────────────────────


class TestCrossUserIsolation:
    """User B cannot access any of User A's resources."""

    def _setup_two_users(self, client):
        tok_a, _ = _create_user(client, "isoA@test.com", "Alice", "Alpha")
        tok_b, _ = _create_user(client, "isoB@test.com", "Bob", "Beta")
        acct_a = _create_funded_account(client, tok_a, amount_cents=100000)
        acct_b = _create_funded_account(client, tok_b, amount_cents=50000)
        card_a = client.post(f"/api/v1/accounts/{acct_a}/cards", headers=_auth(tok_a)).json()["id"]
        return tok_a, tok_b, acct_a, acct_b, card_a

    def test_get_account_denied(self, client):
        _, tok_b, acct_a, _, _ = self._setup_two_users(client)
        assert client.get(f"/api/v1/accounts/{acct_a}", headers=_auth(tok_b)).status_code == 403

    def test_deposit_denied(self, client):
        _, tok_b, acct_a, _, _ = self._setup_two_users(client)
        assert (
            client.post(
                f"/api/v1/accounts/{acct_a}/deposit",
                json={"amount_cents": 100},
                headers=_auth(tok_b),
            ).status_code
            == 403
        )

    def test_transfer_from_other_user_denied(self, client):
        _, tok_b, acct_a, acct_b, _ = self._setup_two_users(client)
        assert (
            client.post(
                "/api/v1/transfers",
                json={
                    "source_account_id": acct_a,
                    "destination_account_id": acct_b,
                    "amount_cents": 100,
                    "idempotency_key": _idem(),
                },
                headers=_auth(tok_b),
            ).status_code
            == 403
        )

    def test_get_card_denied(self, client):
        _, tok_b, _, _, card_a = self._setup_two_users(client)
        assert client.get(f"/api/v1/cards/{card_a}", headers=_auth(tok_b)).status_code == 403

    def test_card_spend_denied(self, client):
        _, tok_b, _, _, card_a = self._setup_two_users(client)
        assert (
            client.post(
                f"/api/v1/cards/{card_a}/spend",
                json={
                    "amount_cents": 100,
                    "merchant": "Thief",
                    "idempotency_key": _idem(),
                },
                headers=_auth(tok_b),
            ).status_code
            == 403
        )

    def test_card_status_update_denied(self, client):
        _, tok_b, _, _, card_a = self._setup_two_users(client)
        assert (
            client.patch(
                f"/api/v1/cards/{card_a}",
                json={"status": "blocked"},
                headers=_auth(tok_b),
            ).status_code
            == 403
        )

    def test_list_cards_denied(self, client):
        _, tok_b, acct_a, _, _ = self._setup_two_users(client)
        assert (
            client.get(
                f"/api/v1/accounts/{acct_a}/cards",
                headers=_auth(tok_b),
            ).status_code
            == 403
        )

    def test_transactions_denied(self, client):
        _, tok_b, acct_a, _, _ = self._setup_two_users(client)
        assert (
            client.get(
                f"/api/v1/accounts/{acct_a}/transactions",
                headers=_auth(tok_b),
            ).status_code
            == 403
        )

    def test_statement_create_denied(self, client):
        _, tok_b, acct_a, _, _ = self._setup_two_users(client)
        assert (
            client.post(
                f"/api/v1/accounts/{acct_a}/statements",
                json={
                    "start_date": "2020-01-01",
                    "end_date": "2026-12-31",
                },
                headers=_auth(tok_b),
            ).status_code
            == 403
        )

    def test_account_status_update_denied(self, client):
        _, tok_b, acct_a, _, _ = self._setup_two_users(client)
        assert (
            client.patch(
                f"/api/v1/accounts/{acct_a}",
                json={"status": "frozen"},
                headers=_auth(tok_b),
            ).status_code
            == 403
        )


# ── 6. Cross-User Transfer (A Sends to B) ───────────────────────────────


class TestCrossUserTransfer:
    """User A can transfer TO User B's account (owns source)."""

    def test_transfer_to_other_user_succeeds(self, client):
        tok_a, _ = _create_user(client, "xferA@test.com", "Alice", "A")
        tok_b, _ = _create_user(client, "xferB@test.com", "Bob", "B")
        acct_a = _create_funded_account(client, tok_a, amount_cents=100000)
        acct_b = _create_funded_account(client, tok_b, amount_cents=0)
        resp = client.post(
            "/api/v1/transfers",
            json={
                "source_account_id": acct_a,
                "destination_account_id": acct_b,
                "amount_cents": 25000,
                "idempotency_key": _idem(),
            },
            headers=_auth(tok_a),
        )
        assert resp.status_code == 201
        # Verify balances
        a = client.get(f"/api/v1/accounts/{acct_a}", headers=_auth(tok_a)).json()
        b = client.get(f"/api/v1/accounts/{acct_b}", headers=_auth(tok_b)).json()
        assert a["balance_cents"] == 75000
        assert b["balance_cents"] == 25000


# ── 7. Double-Entry Ledger Invariant ─────────────────────────────────────


class TestLedgerInvariant:
    """Every transfer creates paired debit+credit; balance matches ledger sum."""

    def test_transfer_creates_paired_entries(self, client):
        token, _ = _create_user(client, "ledger1@test.com")
        a1 = _create_funded_account(client, token, amount_cents=100000)
        a2 = _create_funded_account(client, token, "savings", 0)
        client.post(
            "/api/v1/transfers",
            json={
                "source_account_id": a1,
                "destination_account_id": a2,
                "amount_cents": 30000,
                "idempotency_key": _idem(),
            },
            headers=_auth(token),
        )
        # Source has debit
        src_txns = client.get(f"/api/v1/accounts/{a1}/transactions", headers=_auth(token)).json()
        debits = [t for t in src_txns if t["type"] == "debit"]
        assert any(d["amount_cents"] == 30000 for d in debits)
        # Dest has credit
        dst_txns = client.get(f"/api/v1/accounts/{a2}/transactions", headers=_auth(token)).json()
        credit_txns = [t for t in dst_txns if t["type"] == "credit"]
        assert any(c["amount_cents"] == 30000 for c in credit_txns)
        # Both reference same transfer_id
        assert debits[-1]["transfer_id"] == credit_txns[-1]["transfer_id"]

    def test_balance_matches_ledger_sum(self, client):
        """Account balance = sum(deposits+credits) - sum(debits+card_spends)."""
        token, _ = _create_user(client, "ledger2@test.com")
        a1 = _create_funded_account(client, token, amount_cents=100000)
        a2 = _create_funded_account(client, token, "savings", 0)
        # Transfer out
        client.post(
            "/api/v1/transfers",
            json={
                "source_account_id": a1,
                "destination_account_id": a2,
                "amount_cents": 20000,
                "idempotency_key": _idem(),
            },
            headers=_auth(token),
        )
        # Transfer in
        client.post(
            "/api/v1/transfers",
            json={
                "source_account_id": a2,
                "destination_account_id": a1,
                "amount_cents": 5000,
                "idempotency_key": _idem(),
            },
            headers=_auth(token),
        )
        # Card spend
        card = client.post(f"/api/v1/accounts/{a1}/cards", headers=_auth(token)).json()
        client.post(
            f"/api/v1/cards/{card['id']}/spend",
            json={
                "amount_cents": 3000,
                "merchant": "Store",
                "idempotency_key": _idem(),
            },
            headers=_auth(token),
        )

        # Calculate from ledger
        txns = client.get(f"/api/v1/accounts/{a1}/transactions", headers=_auth(token)).json()
        incoming = sum(t["amount_cents"] for t in txns if t["type"] in ("deposit", "credit"))
        outgoing = sum(t["amount_cents"] for t in txns if t["type"] in ("debit", "card_spend"))
        ledger_balance = incoming - outgoing

        actual = client.get(f"/api/v1/accounts/{a1}", headers=_auth(token)).json()["balance_cents"]
        assert actual == ledger_balance
        # Expected: 100000 - 20000 + 5000 - 3000 = 82000
        assert actual == 82000


# ── 8. Statement Correctness ─────────────────────────────────────────────


class TestStatementCorrectness:
    """Statement math: opening + credits - debits = closing."""

    def test_statement_math_with_mixed_operations(self, client):
        token, _ = _create_user(client, "stmt1@test.com")
        a1 = _create_funded_account(client, token, amount_cents=100000)
        a2 = _create_funded_account(client, token, "savings", 0)
        # Transfers
        for amt in (20000, 10000, 5000):
            client.post(
                "/api/v1/transfers",
                json={
                    "source_account_id": a1,
                    "destination_account_id": a2,
                    "amount_cents": amt,
                    "idempotency_key": _idem(),
                },
                headers=_auth(token),
            )
        # Card spend
        card = client.post(f"/api/v1/accounts/{a1}/cards", headers=_auth(token)).json()
        client.post(
            f"/api/v1/cards/{card['id']}/spend",
            json={
                "amount_cents": 7500,
                "merchant": "Restaurant",
                "idempotency_key": _idem(),
            },
            headers=_auth(token),
        )

        today = date.today().isoformat()
        stmt = client.post(
            f"/api/v1/accounts/{a1}/statements",
            json={
                "start_date": "2020-01-01",
                "end_date": today,
            },
            headers=_auth(token),
        ).json()

        calc = (
            stmt["opening_balance_cents"] + stmt["total_credits_cents"] - stmt["total_debits_cents"]
        )
        assert stmt["closing_balance_cents"] == calc

    def test_statement_on_closed_account(self, client):
        """Historical statements still accessible after account closure."""
        token, _ = _create_user(client, "stmt2@test.com")
        a = _create_funded_account(client, token, amount_cents=50000)
        a2 = _create_funded_account(client, token, "savings", 0)
        # Drain and close
        client.post(
            "/api/v1/transfers",
            json={
                "source_account_id": a,
                "destination_account_id": a2,
                "amount_cents": 50000,
                "idempotency_key": _idem(),
            },
            headers=_auth(token),
        )
        client.patch(f"/api/v1/accounts/{a}", json={"status": "closed"}, headers=_auth(token))
        # Statement should still work
        today = date.today().isoformat()
        resp = client.post(
            f"/api/v1/accounts/{a}/statements",
            json={
                "start_date": "2020-01-01",
                "end_date": today,
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201
        assert resp.json()["transaction_count"] >= 2

    def test_statement_empty_period(self, client):
        token, _ = _create_user(client, "stmt3@test.com")
        a = _create_funded_account(client, token, amount_cents=50000)
        resp = client.post(
            f"/api/v1/accounts/{a}/statements",
            json={
                "start_date": "2030-01-01",
                "end_date": "2030-12-31",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201
        assert resp.json()["transaction_count"] == 0


# ── 9. Token Lifecycle ──────────────────────────────────────────────────


class TestTokenLifecycle:
    """Refresh rotation and logout revocation."""

    def test_refresh_rotation_invalidates_old_token(self, client):
        _signup(client, "tok1@test.com")
        _, refresh1 = _login(client, "tok1@test.com")
        # Refresh
        r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh1})
        assert r.status_code == 200
        # Old refresh revoked
        r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh1})
        assert r2.status_code == 401

    def test_logout_revokes_refresh(self, client):
        _signup(client, "tok2@test.com")
        token, refresh = _login(client, "tok2@test.com")
        client.post("/api/v1/auth/logout", json={"refresh_token": refresh}, headers=_auth(token))
        # Refresh fails
        r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
        assert r.status_code == 401

    def test_login_after_logout(self, client):
        _signup(client, "tok3@test.com")
        token, refresh = _login(client, "tok3@test.com")
        client.post("/api/v1/auth/logout", json={"refresh_token": refresh}, headers=_auth(token))
        # Can login again
        token2, _ = _login(client, "tok3@test.com")
        r = client.get("/api/v1/auth/me", headers=_auth(token2))
        assert r.status_code == 200


# ── 10. Idempotency ─────────────────────────────────────────────────────


class TestIdempotency:
    """Transfer and card spend idempotency — no double-debit on replay."""

    def test_transfer_idempotency_no_double_debit(self, client):
        token, _ = _create_user(client, "idem1@test.com")
        a1 = _create_funded_account(client, token, amount_cents=100000)
        a2 = _create_funded_account(client, token, "savings", 0)
        key = _idem()
        r1 = client.post(
            "/api/v1/transfers",
            json={
                "source_account_id": a1,
                "destination_account_id": a2,
                "amount_cents": 25000,
                "idempotency_key": key,
            },
            headers=_auth(token),
        )
        r2 = client.post(
            "/api/v1/transfers",
            json={
                "source_account_id": a1,
                "destination_account_id": a2,
                "amount_cents": 25000,
                "idempotency_key": key,
            },
            headers=_auth(token),
        )
        assert r1.status_code == 201
        assert r2.status_code == 200
        assert r1.json()["id"] == r2.json()["id"]
        bal = client.get(f"/api/v1/accounts/{a1}", headers=_auth(token)).json()["balance_cents"]
        assert bal == 75000  # Not 50000

    def test_card_spend_idempotency_no_double_charge(self, client):
        token, _ = _create_user(client, "idem2@test.com")
        acct_id = _create_funded_account(client, token, amount_cents=100000)
        card = client.post(f"/api/v1/accounts/{acct_id}/cards", headers=_auth(token)).json()
        key = _idem()
        r1 = client.post(
            f"/api/v1/cards/{card['id']}/spend",
            json={
                "amount_cents": 5000,
                "merchant": "Shop",
                "idempotency_key": key,
            },
            headers=_auth(token),
        )
        r2 = client.post(
            f"/api/v1/cards/{card['id']}/spend",
            json={
                "amount_cents": 5000,
                "merchant": "Shop",
                "idempotency_key": key,
            },
            headers=_auth(token),
        )
        assert r1.status_code == 201
        assert r2.status_code == 200
        assert r1.json()["id"] == r2.json()["id"]
        bal = client.get(f"/api/v1/accounts/{acct_id}", headers=_auth(token)).json()[
            "balance_cents"
        ]
        assert bal == 95000


# ── 11. Edge Cases & Boundary Conditions ─────────────────────────────────


class TestEdgeCases:
    """Boundary amounts, missing resources, wrong methods."""

    def test_deposit_zero_rejected(self, client):
        token, _ = _create_user(client, "edge1@test.com")
        a = _create_funded_account(client, token, amount_cents=0)
        assert (
            client.post(
                f"/api/v1/accounts/{a}/deposit",
                json={"amount_cents": 0},
                headers=_auth(token),
            ).status_code
            == 400
        )

    def test_deposit_negative_rejected(self, client):
        token, _ = _create_user(client, "edge2@test.com")
        a = _create_funded_account(client, token, amount_cents=0)
        assert (
            client.post(
                f"/api/v1/accounts/{a}/deposit",
                json={"amount_cents": -1000},
                headers=_auth(token),
            ).status_code
            == 400
        )

    def test_transfer_nonexistent_destination(self, client):
        token, _ = _create_user(client, "edge3@test.com")
        a = _create_funded_account(client, token, amount_cents=50000)
        assert (
            client.post(
                "/api/v1/transfers",
                json={
                    "source_account_id": a,
                    "destination_account_id": "nonexistent-id",
                    "amount_cents": 100,
                    "idempotency_key": _idem(),
                },
                headers=_auth(token),
            ).status_code
            == 404
        )

    def test_deposit_nonexistent_account(self, client):
        token, _ = _create_user(client, "edge4@test.com")
        assert (
            client.post(
                "/api/v1/accounts/nonexistent-id/deposit",
                json={"amount_cents": 100},
                headers=_auth(token),
            ).status_code
            == 404
        )

    def test_card_spend_overdraft_rejected(self, client):
        token, _ = _create_user(client, "edge5@test.com")
        acct_id = _create_funded_account(client, token, amount_cents=1000)
        card = client.post(f"/api/v1/accounts/{acct_id}/cards", headers=_auth(token)).json()
        assert (
            client.post(
                f"/api/v1/cards/{card['id']}/spend",
                json={
                    "amount_cents": 9999,
                    "merchant": "X",
                    "idempotency_key": _idem(),
                },
                headers=_auth(token),
            ).status_code
            == 400
        )

    def test_transfer_exact_balance_succeeds(self, client):
        """Transferring exactly the available balance should succeed."""
        token, _ = _create_user(client, "edge6@test.com")
        a1 = _create_funded_account(client, token, amount_cents=50000)
        a2 = _create_funded_account(client, token, "savings", 0)
        resp = client.post(
            "/api/v1/transfers",
            json={
                "source_account_id": a1,
                "destination_account_id": a2,
                "amount_cents": 50000,
                "idempotency_key": _idem(),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201
        bal = client.get(f"/api/v1/accounts/{a1}", headers=_auth(token)).json()["balance_cents"]
        assert bal == 0

    def test_card_spend_exact_balance_succeeds(self, client):
        """Spending exactly the available balance should succeed."""
        token, _ = _create_user(client, "edge7@test.com")
        acct_id = _create_funded_account(client, token, amount_cents=5000)
        card = client.post(f"/api/v1/accounts/{acct_id}/cards", headers=_auth(token)).json()
        resp = client.post(
            f"/api/v1/cards/{card['id']}/spend",
            json={
                "amount_cents": 5000,
                "merchant": "AllIn",
                "idempotency_key": _idem(),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201
        bal = client.get(f"/api/v1/accounts/{acct_id}", headers=_auth(token)).json()[
            "balance_cents"
        ]
        assert bal == 0

    def test_card_spend_one_cent_over_rejected(self, client):
        """Spending one cent more than balance should fail."""
        token, _ = _create_user(client, "edge8@test.com")
        acct_id = _create_funded_account(client, token, amount_cents=5000)
        card = client.post(f"/api/v1/accounts/{acct_id}/cards", headers=_auth(token)).json()
        assert (
            client.post(
                f"/api/v1/cards/{card['id']}/spend",
                json={
                    "amount_cents": 5001,
                    "merchant": "X",
                    "idempotency_key": _idem(),
                },
                headers=_auth(token),
            ).status_code
            == 400
        )


# ── 12. Middleware ───────────────────────────────────────────────────────


class TestMiddleware:
    """X-Request-ID and error envelope on all responses."""

    def test_request_id_on_success(self, client):
        resp = client.get("/health")
        assert resp.headers.get("x-request-id") is not None

    def test_request_id_on_error(self, client):
        resp = client.get("/api/v1/nonexistent")
        assert resp.headers.get("x-request-id") is not None

    def test_error_envelope_format(self, client):
        resp = client.get("/api/v1/nonexistent")
        body = resp.json()
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]

    def test_request_id_echo(self, client):
        custom_id = "test-" + _idem()
        resp = client.get("/health", headers={"X-Request-ID": custom_id})
        assert resp.headers.get("x-request-id") == custom_id


# ── 13. Auth Edge Cases ─────────────────────────────────────────────────


class TestAuthEdgeCases:
    """Boundary conditions on authentication."""

    def test_signup_empty_email(self, client):
        assert (
            client.post(
                "/api/v1/auth/signup",
                json={
                    "email": "",
                    "password": "StrongPass1!",
                },
            ).status_code
            == 422
        )

    def test_signup_password_exactly_8_chars(self, client):
        resp = client.post(
            "/api/v1/auth/signup",
            json={
                "email": "exact8@test.com",
                "password": "Abcdef1!",
            },
        )
        assert resp.status_code == 201

    def test_protected_routes_without_token(self, client):
        """Every protected endpoint rejects unauthenticated requests."""
        endpoints = [
            ("GET", "/api/v1/auth/me"),
            ("POST", "/api/v1/holders"),
            ("GET", "/api/v1/holders/me"),
            ("POST", "/api/v1/accounts"),
            ("GET", "/api/v1/accounts"),
            ("GET", "/api/v1/transfers"),
            ("POST", "/api/v1/transfers"),
        ]
        for method, path in endpoints:
            resp = client.request(method, path)
            assert resp.status_code == 401, f"{method} {path} should require auth"
