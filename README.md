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

# Docker test stages
docker build --target test -t banking-test .
docker run --rm banking-test
docker build --target e2e -t banking-e2e .
docker run --rm banking-e2e
```

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

See `.env.example` for all configuration options.

## Documentation

- [PRD.MD](PRD.MD) — Full implementation plan and acceptance criteria
- [docs/AI_USAGE.md](docs/AI_USAGE.md) — AI-driven development evidence log
- [docs/INDEX.md](docs/INDEX.md) — Documentation graph index
- [CLAUDE.md](CLAUDE.md) — AI agent guidance for this repo
