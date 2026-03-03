# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A production-ready banking service API built with FastAPI and SQLite. Implements signup, authentication, account holders, accounts, transfers (double-entry ledger), cards, and statements. This is an assessment project — production readiness, AI-driven development evidence, and traceability are key judging dimensions.

## Commands

```bash
# Run dev server
uv run uvicorn app.main:app --reload

# Run all API tests with coverage
uv run --with pytest,httpx,pytest-cov pytest tests/ -v --ignore=tests/test_playwright.py --cov=app --cov-report=term-missing

# Run a single test file
uv run --with pytest,httpx pytest tests/test_health.py -v

# Run a single test
uv run --with pytest,httpx pytest tests/test_health.py::test_health_returns_healthy -v

# Lint and format
uv run --with ruff ruff check app/ tests/
uv run --with ruff ruff format app/ tests/

# Browser E2E (Playwright)
uv run --with pytest,playwright,httpx pytest tests/test_playwright.py -v

# Demo client (end-to-end flow)
uv run scripts/test_client.py

# Docker
docker compose up --build
```

## Architecture

Strict layered architecture — dependencies flow downward only:

```
routers (HTTP contract) → services (business rules) → models (ORM) → database.py (engine)
                                                     ↗
schemas (Pydantic contracts) ────────────────────────
auth (JWT deps) ────────────────────────────────────→ services
middleware (request ID, logging, errors) ───────────→ routers
```

- **`app/routers/`** — HTTP handlers only. No business logic. Parse request, call service, return response.
- **`app/services/`** — All business rules and invariants. Ownership validation happens here.
- **`app/models/`** — SQLAlchemy ORM models. All monetary fields use integer cents (`*_cents`).
- **`app/schemas/`** — Pydantic request/response contracts. Shared between routers and services.
- **`app/auth/`** — JWT access/refresh token creation, validation, and FastAPI dependencies.
- **`app/middleware/`** — `X-Request-ID` correlation, access logging, unified error handler.
- **`app/database.py`** — SQLite engine with WAL mode, foreign keys, busy_timeout pragmas. Provides `get_db` dependency.
- **`app/config.py`** — pydantic-settings loaded from `.env`. Single `settings` instance.
- **`app/logging_config.py`** — JSON structured logging to stdout with request context fields.
- **`app/main.py`** — App factory with lifespan (init_db on startup, dispose_db on shutdown).

## Key Design Invariants

- **Integer cents only** — all monetary values stored as `*_cents` columns, never floats.
- **Double-entry ledger** — every transfer creates both a debit and credit transaction record.
- **Atomic overdraft prevention** — balance checks use guarded SQL UPDATE (not check-then-act).
- **Idempotency keys** — all write paths (transfers, card spends) are idempotent via app-layer lookup + DB UNIQUE constraint + IntegrityError reconciliation.
- **Ownership enforcement** — every protected resource access is validated in the service layer, not just at the router.
- **API versioning** — all domain routes under `/api/v1/`.

## Test Infrastructure

Tests use an isolated SQLite DB (`test_banking.db`). The `conftest.py` autouse fixture creates fresh tables before each test and drops them after, overriding `get_db` with a test session. The `client` fixture provides a `TestClient` with the DB override wired in.

Coverage minimum is 80% (configured in pyproject.toml).

## Documentation Requirements

Every significant change must be traced in:
- **`docs/AI_USAGE.md`** — AI prompts, iterations, what failed, what was corrected, manual decisions.
- **`docs/INDEX.md`** — RAG-graph style index with document nodes, relationship edges, and retrieval tags. Update when adding/changing docs.
- **`REQUIREMENTS.MD`** — canonical implementation plan. Sections 4.1–4.15 define workstreams; sections 9–15 contain embedded checklists (security, release, SLO, runbooks, demo evidence, traceability matrix).
