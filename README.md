# Banking Service

Production-ready banking API built with FastAPI and SQLite.

## Features

- User signup, authentication (JWT access + refresh tokens)
- Account holders and accounts (CRUD + status management)
- Money transfers with double-entry ledger and idempotency
- Card issuance and card spend transactions
- Statement generation by account and period
- Structured JSON logging with request correlation
- Health/readiness probes and graceful shutdown
- Containerized with Docker (multi-stage build)

## Quick Start

```bash
# Install dependencies
uv sync

# Run locally
uv run uvicorn app.main:app --reload

# Run tests
uv run --with pytest,httpx,pytest-cov pytest tests/ -v --cov=app --cov-report=term-missing

# Lint
uv run --with ruff ruff check app/ tests/

# Docker
docker compose up --build
```

## Project Structure

```
app/
  auth/          — JWT auth primitives and dependencies
  middleware/    — request ID, logging, error handling
  models/        — SQLAlchemy ORM models
  routers/       — FastAPI route handlers
  schemas/       — Pydantic request/response contracts
  services/      — business logic layer
  config.py      — settings from environment
  database.py    — engine, session, SQLite pragmas
  logging_config.py — structured JSON logging
  main.py        — app factory and lifecycle
tests/           — pytest test suite
docs/            — documentation and AI usage logs
scripts/         — demo client and seed data
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness probe |
| GET | `/ready` | Readiness probe (DB check) |

*More endpoints added as implementation progresses.*

## Environment Variables

See `.env.example` for all configuration options.

## Documentation

- [REQUIREMENTS.MD](REQUIREMENTS.MD) — Full implementation plan
- [docs/AI_USAGE.md](docs/AI_USAGE.md) — AI-driven development log
- [docs/INDEX.md](docs/INDEX.md) — Documentation graph index
