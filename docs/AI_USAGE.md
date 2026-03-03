# AI Usage Report

This document tracks AI-driven development decisions, prompts, iterations, and evidence
as required by the assessment criteria.

## Tools and Models

| Tool | Model | Purpose |
|------|-------|---------|
| Claude Code (CLI) | claude-opus-4-6 | Primary development agent — scaffolding, implementation, tests, docs |

## Development Log

### Session 1: Project Initialization (2026-03-03)

**Objective:** Initialize repo, scaffold project structure, create foundation files.

**Agent actions (GSD skill, verification-gated):**

1. **Git init** — Initialized repo, renamed branch to `main`.
2. **Repo basics** — Created `.gitignore` (Python, IDE, DB, env exclusions), `.env.example` with all config keys.
3. **Directory scaffold** — Created `app/` layered structure per REQUIREMENTS.MD Section 2:
   - `app/routers/` — HTTP handlers
   - `app/services/` — business logic
   - `app/models/` — SQLAlchemy ORM
   - `app/schemas/` — Pydantic contracts
   - `app/auth/` — JWT auth primitives
   - `app/middleware/` — cross-cutting concerns
4. **pyproject.toml** — FastAPI, SQLAlchemy, Pydantic, JWT, bcrypt, uvicorn + dev/e2e extras.
5. **Core files created:**
   - `app/config.py` — pydantic-settings from env
   - `app/database.py` — SQLite engine with WAL/FK/busy_timeout pragmas, session lifecycle
   - `app/logging_config.py` — JSON structured log formatter to stdout
   - `app/main.py` — app factory with lifespan (init_db/dispose_db)
   - `app/routers/health.py` — `/health` (liveness) + `/ready` (DB-backed readiness)
6. **Test infrastructure:**
   - `tests/conftest.py` — isolated test DB with per-test table create/drop
   - `tests/test_health.py` — health + readiness endpoint tests
7. **Containerization:**
   - `Dockerfile` — multi-stage build, non-root user, HEALTHCHECK
   - `docker-compose.yml` — volume-backed DB, env_file, health checks
8. **Scripts:** `scripts/test_client.py` (demo client), `scripts/seed_data.py` (placeholder)
9. **Documentation:** README.md, this AI_USAGE.md, docs/INDEX.md

**Verification:** `pytest tests/test_health.py` — both tests pass.

**Manual decisions:**
- Chose integer cents for monetary values (not floats) per requirements Section 2.
- Chose WAL + busy_timeout=5000ms for SQLite pragmas to handle concurrent reads.
- Structured JSON logging to stdout (not file-based) for container compatibility.

---

*Subsequent sessions will be appended below with the same evidence format.*
