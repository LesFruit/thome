# Banking Service

Production-ready banking API built with FastAPI and SQLite.

## Features

- User signup, authentication (JWT access + refresh tokens with rotation)
- Account holders (KYC profile) and accounts (checking/savings, status management)
- Money transfers with double-entry ledger, atomic overdraft prevention, and idempotency
- Card issuance, status management, and card spend transactions
- Statement generation with period-based balance calculations
- Structured JSON logging with X-Request-ID correlation
- Health/readiness probes and graceful shutdown
- Consistent error envelopes (no traceback leakage)
- Frontend dashboard with guided flow and ops/reviewer panel
- Containerized with Docker (multi-stage build, non-root, HEALTHCHECK)

## Quick Start

```bash
# Run locally
uv run uvicorn app.main:app --reload

# Open dashboard
open http://localhost:8000/dashboard

# Run tests
uv run --with pytest,httpx,email-validator,pytest-cov pytest tests/ -v --cov=app --cov-report=term-missing

# Lint
uv run --with ruff ruff check app/ tests/
uv run --with ruff ruff format --check app/ tests/

# Install browser for Playwright E2E
uv run --with playwright playwright install chromium

# Run Playwright E2E
uv run --with pytest,playwright,httpx pytest tests/test_playwright.py -v

# E2E demo client
uv run scripts/test_client.py

# Docker
docker compose up --build
# Fallback for older Docker installs
docker-compose up --build

# Docker test stages
docker build --target test -t banking-test .
docker run --rm banking-test
docker build --target e2e -t banking-e2e .
docker run --rm banking-e2e
```

`docker compose up --build` works without creating a `.env` file; safe development defaults are included in `docker-compose.yml`.
Use `.env` only if you want to override defaults.

## Docker Validation (No `.env` Required)

Use this sequence to verify the full containerized workflow:

```bash
# 1) Run full backend test suite in Docker
docker build --target test -t banking-test .
docker run --rm banking-test

# 2) Run runtime image and verify probes
docker build --target runtime -t banking-runtime .
docker run -d --name banking-runtime-check -p 8000:8000 banking-runtime
curl -sf http://localhost:8000/health
curl -sf http://localhost:8000/ready
docker rm -f banking-runtime-check

# 3) Run Playwright E2E in Docker
docker build --target e2e -t banking-e2e .
docker run --rm banking-e2e

# 4) Verify Docker Compose startup path
docker compose up --build -d
curl -sf http://localhost:8000/health
curl -sf http://localhost:8000/ready
docker compose down
```

If your environment uses legacy Compose, replace `docker compose` with `docker-compose`.

## MVP Readiness

This project is ready as an MVP for the assessment scope:

- Core domains implemented end-to-end: auth, holders/accounts, transfers, cards, statements.
- Financial integrity guards are in place: atomic balance updates, overdraft prevention, idempotency keys, ownership enforcement.
- Operational baseline is implemented: structured logging, request correlation, health/readiness endpoints, graceful shutdown, Dockerized deployment.
- Validation gates are strong: `229` tests passing with `95.16%` coverage (`>=80%` required), plus Playwright E2E coverage in local and Docker flows.
- Documentation is complete for handoff: setup/run instructions, PRD, AI usage evidence, and traceability index.

## API Endpoints

### Health
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness probe |
| GET | `/ready` | Readiness probe (DB check) |
| GET | `/dashboard` | Frontend dashboard |

### Auth (`/api/v1/auth`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/signup` | Create account |
| POST | `/login` | Get access + refresh tokens |
| POST | `/refresh` | Rotate refresh token |
| POST | `/logout` | Revoke refresh token |
| GET | `/me` | Current user profile |

### Holders (`/api/v1/holders`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/` | Create holder profile |
| GET | `/me` | Get your holder profile |
| PATCH | `/me` | Update holder fields |

### Accounts (`/api/v1/accounts`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/` | Open new account |
| GET | `/` | List your accounts |
| GET | `/{id}` | Get account details |
| PATCH | `/{id}` | Update account status |
| POST | `/{id}/deposit` | Deposit funds |
| GET | `/{id}/transactions` | List account transactions |
| POST | `/{id}/cards` | Issue card for account |
| GET | `/{id}/cards` | List cards for account |
| POST | `/{id}/statements` | Generate statement |
| GET | `/{id}/statements` | List statements |

### Transfers (`/api/v1/transfers`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/` | Create transfer (idempotent) |
| GET | `/` | List your transfers |
| GET | `/{id}` | Get transfer details |

### Cards (`/api/v1/cards`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/{id}` | Get card details |
| PATCH | `/{id}` | Update card status |
| POST | `/{id}/spend` | Card spend (idempotent) |

### Statements (`/api/v1/statements`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/{id}` | Get statement details |

## Environment Variables

See `.env.example` for all configuration options and overrides.
For Docker Compose, `.env` is optional because defaults are already provided.

### When `.env` Is Required (Production)

Use a real `.env` (or secret manager-backed env injection) for any production/staging deployment.  
The defaults in `docker-compose.yml` are development-safe convenience values, not production settings.

At minimum, set:
- `JWT_SECRET_KEY` to a strong, unique secret
- `DATABASE_URL` to your production database path/connection
- `APP_ENV=production` and `DEBUG=false`
- Any environment-specific host/port and token lifetime settings

Do not commit `.env` files with real secrets.

## Documentation

- [PRD.MD](PRD.MD) — Full implementation plan and acceptance criteria
- [docs/AI_USAGE.md](docs/AI_USAGE.md) — AI-driven development evidence log
- [docs/INDEX.md](docs/INDEX.md) — Documentation graph index
- [CLAUDE.md](CLAUDE.md) — AI agent guidance for this repo
