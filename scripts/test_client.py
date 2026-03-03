#!/usr/bin/env python3
"""End-to-end demo client exercising the full banking API flow.

Usage: uv run scripts/test_client.py [--base-url http://localhost:8000]
"""
# /// script
# dependencies = ["httpx", "click"]
# ///

import uuid
import click
import httpx
import sys


@click.command()
@click.option("--base-url", default="http://localhost:8000", help="API base URL")
def main(base_url: str):
    """Run full banking flow: signup -> holder -> account -> transfer -> card -> statement."""
    c = httpx.Client(base_url=base_url, timeout=30)

    # 1. Health checks
    r = c.get("/health")
    assert r.status_code == 200, f"Health failed: {r.text}"
    click.echo(f"[OK] Health: {r.json()}")

    r = c.get("/ready")
    assert r.status_code == 200, f"Ready failed: {r.text}"
    click.echo(f"[OK] Ready: {r.json()}")

    # 2. Signup
    email = f"demo-{uuid.uuid4().hex[:8]}@test.com"
    r = c.post("/api/v1/auth/signup", json={"email": email, "password": "DemoPass123!"})
    assert r.status_code == 201, f"Signup failed: {r.text}"
    click.echo(f"[OK] Signup: {email}")

    # 3. Login
    r = c.post("/api/v1/auth/login", json={"email": email, "password": "DemoPass123!"})
    assert r.status_code == 200, f"Login failed: {r.text}"
    tokens = r.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    click.echo(f"[OK] Login: got tokens")

    # 4. Get current user
    r = c.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200
    click.echo(f"[OK] Auth/me: {r.json()['email']}")

    # 5. Create holder
    r = c.post("/api/v1/holders", json={
        "first_name": "Demo", "last_name": "User", "date_of_birth": "1990-06-15",
    }, headers=headers)
    assert r.status_code == 201
    click.echo(f"[OK] Holder created: {r.json()['id'][:8]}")

    # 6. Create two accounts
    r1 = c.post("/api/v1/accounts", json={"account_type": "checking"}, headers=headers)
    r2 = c.post("/api/v1/accounts", json={"account_type": "savings"}, headers=headers)
    assert r1.status_code == 201 and r2.status_code == 201
    acct1 = r1.json()["id"]
    acct2 = r2.json()["id"]
    click.echo(f"[OK] Accounts: checking={acct1[:8]}, savings={acct2[:8]}")

    # 7. Deposit
    r = c.post(f"/api/v1/accounts/{acct1}/deposit", json={"amount_cents": 100000}, headers=headers)
    assert r.status_code == 200
    click.echo(f"[OK] Deposited $1000 into checking")

    # 8. Transfer
    r = c.post("/api/v1/transfers", json={
        "source_account_id": acct1,
        "destination_account_id": acct2,
        "amount_cents": 25000,
        "idempotency_key": str(uuid.uuid4()),
    }, headers=headers)
    assert r.status_code == 201
    click.echo(f"[OK] Transfer: $250 checking→savings")

    # 9. Verify balances
    r1 = c.get(f"/api/v1/accounts/{acct1}", headers=headers)
    r2 = c.get(f"/api/v1/accounts/{acct2}", headers=headers)
    assert r1.json()["balance_cents"] == 75000
    assert r2.json()["balance_cents"] == 25000
    click.echo(f"[OK] Balances: checking=$750, savings=$250")

    # 10. Issue card + spend
    r = c.post(f"/api/v1/accounts/{acct1}/cards", headers=headers)
    assert r.status_code == 201
    card_id = r.json()["id"]
    click.echo(f"[OK] Card issued: {r.json()['card_number']}")

    r = c.post(f"/api/v1/cards/{card_id}/spend", json={
        "amount_cents": 5000,
        "merchant": "Demo Coffee Shop",
        "idempotency_key": str(uuid.uuid4()),
    }, headers=headers)
    assert r.status_code == 201
    click.echo(f"[OK] Card spend: $50 at Demo Coffee Shop")

    # 11. Generate statement
    from datetime import date
    r = c.post(f"/api/v1/accounts/{acct1}/statements", json={
        "start_date": "2020-01-01",
        "end_date": date.today().isoformat(),
    }, headers=headers)
    assert r.status_code == 201
    stmt = r.json()
    click.echo(f"[OK] Statement: {stmt['transaction_count']} txns, closing=${ stmt['closing_balance_cents']/100:.2f}")

    # 12. Refresh token
    r = c.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    click.echo(f"[OK] Token refresh: new tokens issued")

    # 13. Logout
    new_tokens = r.json()
    r = c.post("/api/v1/auth/logout", json={"refresh_token": new_tokens["refresh_token"]},
               headers={"Authorization": f"Bearer {new_tokens['access_token']}"})
    assert r.status_code == 200
    click.echo(f"[OK] Logout: refresh token revoked")

    click.echo(f"\n{'='*50}")
    click.echo(f"FULL E2E FLOW PASSED — all 13 steps completed")
    click.echo(f"{'='*50}")


if __name__ == "__main__":
    main()
