#!/usr/bin/env python3
"""Seed development database with sample data for demos.

Creates a demo user with holder, accounts, deposits, transfers, cards, and statements.

Usage: uv run scripts/seed_data.py
"""
# /// script
# dependencies = ["httpx", "fastapi", "uvicorn", "sqlalchemy", "pydantic", "pydantic-settings", "python-jose[cryptography]", "bcrypt", "python-multipart", "python-dateutil", "email-validator"]
# ///

import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, timedelta

import httpx

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")


def main():
    client = httpx.Client(base_url=BASE_URL, timeout=10)

    print("=== Banking Service — Seed Data ===\n")

    # 1. Signup
    resp = client.post("/api/v1/auth/signup", json={
        "email": "demo@bankingservice.dev",
        "password": "DemoPass123!",
    })
    if resp.status_code == 201:
        print(f"[1] Signup: {resp.json()['email']}")
    elif resp.status_code == 409:
        print("[1] Signup: user already exists (skipping)")
    else:
        print(f"[1] Signup failed: {resp.status_code} {resp.text}")
        return

    # 2. Login
    resp = client.post("/api/v1/auth/login", json={
        "email": "demo@bankingservice.dev",
        "password": "DemoPass123!",
    })
    tokens = resp.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    print(f"[2] Login: token obtained")

    # 3. Create holder
    resp = client.post("/api/v1/holders", json={
        "first_name": "Demo",
        "last_name": "User",
        "date_of_birth": "1990-06-15",
    }, headers=headers)
    if resp.status_code == 201:
        print(f"[3] Holder: {resp.json()['first_name']} {resp.json()['last_name']}")
    elif resp.status_code == 409:
        print("[3] Holder: already exists (skipping)")
    else:
        print(f"[3] Holder failed: {resp.status_code}")

    # 4. Create checking account
    resp = client.post("/api/v1/accounts", json={"account_type": "checking"}, headers=headers)
    checking = resp.json()
    print(f"[4] Checking account: {checking['id']}")

    # 5. Create savings account
    resp = client.post("/api/v1/accounts", json={"account_type": "savings"}, headers=headers)
    savings = resp.json()
    print(f"[5] Savings account: {savings['id']}")

    # 6. Deposit $5000 into checking
    resp = client.post(
        f"/api/v1/accounts/{checking['id']}/deposit",
        json={"amount_cents": 500_000},
        headers=headers,
    )
    print(f"[6] Deposit: $5000.00 → checking (balance: ${resp.json()['balance_cents'] / 100:.2f})")

    # 7. Transfer $1000 checking → savings
    resp = client.post("/api/v1/transfers", json={
        "source_account_id": checking["id"],
        "destination_account_id": savings["id"],
        "amount_cents": 100_000,
        "idempotency_key": str(uuid.uuid4()),
    }, headers=headers)
    print(f"[7] Transfer: $1000.00 checking → savings")

    # 8. Transfer $500 checking → savings
    resp = client.post("/api/v1/transfers", json={
        "source_account_id": checking["id"],
        "destination_account_id": savings["id"],
        "amount_cents": 50_000,
        "idempotency_key": str(uuid.uuid4()),
    }, headers=headers)
    print(f"[8] Transfer: $500.00 checking → savings")

    # 9. Issue card on checking
    resp = client.post(f"/api/v1/accounts/{checking['id']}/cards", headers=headers)
    card = resp.json()
    print(f"[9] Card issued: ****{card['card_number'][-4:]}")

    # 10. Card spend $50
    resp = client.post(f"/api/v1/cards/{card['id']}/spend", json={
        "amount_cents": 5_000,
        "merchant": "Coffee House",
        "idempotency_key": str(uuid.uuid4()),
    }, headers=headers)
    print(f"[10] Card spend: $50.00 at Coffee House")

    # 11. Card spend $125
    resp = client.post(f"/api/v1/cards/{card['id']}/spend", json={
        "amount_cents": 12_500,
        "merchant": "Online Store",
        "idempotency_key": str(uuid.uuid4()),
    }, headers=headers)
    print(f"[11] Card spend: $125.00 at Online Store")

    # 12. Generate statement
    today = date.today()
    start = today - timedelta(days=30)
    resp = client.post(f"/api/v1/accounts/{checking['id']}/statements", json={
        "start_date": start.isoformat(),
        "end_date": today.isoformat(),
    }, headers=headers)
    stmt = resp.json()
    print(f"[12] Statement: {stmt['transaction_count']} txns, "
          f"balance ${stmt['closing_balance_cents'] / 100:.2f}")

    # 13. Verify balances
    c = client.get(f"/api/v1/accounts/{checking['id']}", headers=headers).json()
    s = client.get(f"/api/v1/accounts/{savings['id']}", headers=headers).json()
    print(f"\n=== Final Balances ===")
    print(f"Checking: ${c['balance_cents'] / 100:.2f}")
    print(f"Savings:  ${s['balance_cents'] / 100:.2f}")
    print(f"Total:    ${(c['balance_cents'] + s['balance_cents']) / 100:.2f}")
    print(f"\nSeed complete. Login: demo@bankingservice.dev / DemoPass123!")


if __name__ == "__main__":
    main()
