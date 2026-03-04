#!/usr/bin/env python3
"""Quick SLO/SLI latency benchmark for section 13 of PRD.MD."""
# /// script
# dependencies = ["httpx", "fastapi", "uvicorn", "sqlalchemy", "pydantic", "pydantic-settings", "python-jose[cryptography]", "bcrypt", "python-multipart", "python-dateutil", "email-validator"]
# ///

import os
import statistics
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

DB_PATH = "./bench_slo.db"
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _pragmas(conn, _rec):
    c = conn.cursor()
    for stmt in ["PRAGMA journal_mode=WAL", "PRAGMA synchronous=NORMAL",
                 "PRAGMA foreign_keys=ON", "PRAGMA busy_timeout=5000"]:
        c.execute(stmt)
    c.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def _get_db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


app.dependency_overrides[get_db] = _get_db
client = TestClient(app)


def bench(method, path, n=100, **kwargs):
    latencies = []
    for _ in range(n):
        t0 = time.perf_counter()
        getattr(client, method)(path, **kwargs)
        latencies.append((time.perf_counter() - t0) * 1000)
    return {
        "p50": statistics.median(latencies),
        "p95": sorted(latencies)[int(n * 0.95)],
        "p99": sorted(latencies)[int(n * 0.99)],
    }


def main():
    print("SLO/SLI Benchmark — Banking Service")
    print("=" * 60)

    # Health (liveness)
    r = bench("get", "/health")
    print(f"Health:   p50={r['p50']:.1f}ms  p95={r['p95']:.1f}ms  p99={r['p99']:.1f}ms")

    # Ready (readiness)
    r = bench("get", "/ready")
    print(f"Ready:    p50={r['p50']:.1f}ms  p95={r['p95']:.1f}ms  p99={r['p99']:.1f}ms")

    # Signup
    client.post("/api/v1/auth/signup", json={"email": "bench@t.com", "password": "StrongPass1!"})

    # Login (write)
    r = bench("post", "/api/v1/auth/login", n=50,
              json={"email": "bench@t.com", "password": "StrongPass1!"})
    print(f"Login:    p50={r['p50']:.1f}ms  p95={r['p95']:.1f}ms  p99={r['p99']:.1f}ms")

    # Auth/me (read)
    login = client.post("/api/v1/auth/login",
                        json={"email": "bench@t.com", "password": "StrongPass1!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    r = bench("get", "/api/v1/auth/me", headers=headers)
    print(f"Read:     p50={r['p50']:.1f}ms  p95={r['p95']:.1f}ms  p99={r['p99']:.1f}ms")

    # Setup accounts for write benchmarks
    client.post("/api/v1/holders", json={
        "first_name": "B", "last_name": "U", "date_of_birth": "1990-01-01",
    }, headers=headers)
    a1 = client.post("/api/v1/accounts", json={"account_type": "checking"}, headers=headers).json()
    a2 = client.post("/api/v1/accounts", json={"account_type": "savings"}, headers=headers).json()
    client.post(f"/api/v1/accounts/{a1['id']}/deposit",
                json={"amount_cents": 50_000_000}, headers=headers)

    # Transfer (write)
    latencies = []
    for _ in range(50):
        t0 = time.perf_counter()
        client.post("/api/v1/transfers", json={
            "source_account_id": a1["id"],
            "destination_account_id": a2["id"],
            "amount_cents": 100,
            "idempotency_key": str(uuid.uuid4()),
        }, headers=headers)
        latencies.append((time.perf_counter() - t0) * 1000)
    p50 = statistics.median(latencies)
    p95 = sorted(latencies)[int(50 * 0.95)]
    p99 = sorted(latencies)[int(50 * 0.99)]
    print(f"Transfer: p50={p50:.1f}ms  p95={p95:.1f}ms  p99={p99:.1f}ms")

    print("=" * 60)

    # Cleanup
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists(DB_PATH):
        os.unlink(DB_PATH)


if __name__ == "__main__":
    main()
