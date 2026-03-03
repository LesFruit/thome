# AI Usage Report

This document tracks AI-driven development decisions, prompts, iterations, and evidence
as required by the assessment criteria.

## Tools and Models

| Tool | Model | Purpose |
|------|-------|---------|
| Claude Code (CLI) | claude-opus-4-6 | Primary development agent — scaffolding, implementation, tests, docs |

## Methodology

**Test-Driven Development (TDD)** applied throughout:
1. Write failing tests first (red phase)
2. Implement minimum code to pass (green phase)
3. Run full suite to verify zero regressions
4. Commit with meaningful message linking to REQUIREMENTS.MD section

Every commit message references the requirement section it satisfies.

## Development Log

### Session 1: Project Initialization (2026-03-03)

**Commit:** `ccff3f8` — feat: initialize banking service project with full scaffold

**Actions:** Git init, directory scaffold, pyproject.toml, config, database (WAL pragmas), logging, health/readiness probes, Dockerfile, docker-compose, test infrastructure, docs.

**Tests:** 2 pass (health + readiness). **Covers:** 4.1, 4.8, 4.9 (partial), 4.11 (partial).

### Session 2: Middleware + Error Handlers (2026-03-03)

**Commit:** `2ffe7b6` — feat(4.1): add request-ID middleware, error envelopes, process time

**TDD:** 6 tests written first (5 red → 5 green).
- RequestIDMiddleware: X-Request-ID + X-Process-Time headers
- Unified error handler: consistent `{error: {code, message}}` envelopes
- No traceback leakage in responses

**Tests:** 8 pass. **Covers:** 4.1 complete.

### Session 3: Auth and Identity (2026-03-03)

**Commit:** `f8f7639` — feat(4.2): implement auth — signup, login, refresh rotation, logout, JWT

**TDD:** 12 tests written first (all red → all green).
- User + RefreshToken models, bcrypt hashing, JWT with jti claims
- Refresh rotation: old token revoked, new issued
- Generic "Invalid credentials" on failure (no info leakage)

**Iteration:** passlib incompatible with Python 3.13 → switched to direct `bcrypt` library.
JWT refresh tokens had identical payloads within same second → added `jti` (uuid4) claim.

**Tests:** 20 pass. **Covers:** 4.2 complete.

### Session 4: Account Holders + Accounts (2026-03-03)

**Commit:** `fbcdad9` — feat(4.3): implement account holders and accounts with ownership enforcement

**TDD:** 13 tests written first (all red → all green).
- AccountHolder (KYC fields), Account (type, status, balance_cents)
- Status transitions: active↔frozen→closed (terminal), invalid transitions rejected
- Cross-user access denied (403)

**Tests:** 33 pass. **Covers:** 4.3 complete.

### Session 5: Transfers + Transactions (2026-03-03)

**Commit:** `673eae4` — feat(4.4): implement transfers with double-entry ledger and idempotency

**TDD:** 9 tests written first (all red → all green).
- Atomic guarded SQL UPDATE for overdraft prevention (not check-then-act)
- Double-entry: debit + credit Transaction records per transfer
- Idempotency: UNIQUE constraint + app-layer check, replay returns original
- Self-transfer rejection, insufficient funds, cross-user denial

**Tests:** 42 pass. **Covers:** 4.4 complete.

### Session 6: Cards + Card Spend (2026-03-03)

**Commit:** `8fd6f2e` — feat(4.5): implement cards with state machines and idempotent card spend

**TDD:** 12 tests written first (all red → all green).
- Card state machine: active→blocked/cancelled (terminal)
- Card spend: validates card status + account status + expiry + balance
- Atomic guarded debit, idempotency, cross-user denial

**Tests:** 54 pass. **Covers:** 4.5 complete.

### Session 7: Statements (2026-03-03)

**Commit:** `08b43ae` — feat(4.6): implement statements with period calculations

**TDD:** 5 tests written first (all red → all green).
- Pre-period balance (opening), in-period totals, closing balance
- All transaction types: debit, credit, deposit, card_spend
- Unauthorized access denied

**Tests:** 59 pass. **Covers:** 4.6 complete.

### Session 8: Logging Tests + Frontend (2026-03-03)

**Commits:** `c423a59` (logging tests), `73d9171` (frontend)
- 5 logging verification tests (JSON format, context fields, sanitization)
- Single HTML dashboard with guided flow + reviewer/ops panel

**Tests:** 64 pass. **Covers:** 4.7, 4.10 complete.

### Session 9: Documentation + Test Client (2026-03-03)

**Commit:** `22400a7` — docs(4.11): update all documentation

Full E2E demo client (13-step flow), updated README, AI_USAGE, INDEX, CLAUDE.md.

**Tests:** 64 pass. **Covers:** 4.11 complete.

### Session 10: Lint Fixes + CI + Stress Tests (2026-03-03)

**Commits:** `5716e96` (lint), `58c4cc2` (CI + stress)

- Fixed all ruff violations: line length, import ordering, SQLAlchemy `.is_(False)`, UTC aliases
- Created `.github/workflows/validate.yml` CI pipeline (lint, test with 80% gate, docker smoke)
- Wrote 6 stress/concurrency tests with per-request session factory for thread safety
- Tests cover: concurrent overdraft prevention, idempotency under contention, ledger invariants

**Tests:** 70 pass, 94% coverage. **Covers:** 4.12, section 5 complete.

### Session 11: Security, SLO, Traceability (2026-03-03)

**Commit:** `6fb8bae` — docs(9,12,13,15): complete all embedded checklists

- Executed security validation: secrets scan, auth negatives, log leakage (section 9)
- Filled release checklist: 9/10 gates passed (section 12)
- Ran SLO benchmark: all targets met — health p95=4.6ms, read p95=9ms, write p95=230ms (section 13)
- Completed traceability matrix: 12 requirement rows with code paths, tests, evidence (section 15)

**Tests:** 70 pass. **Covers:** 4.12–4.15 complete.

### Session 12: Frontend Dashboard + E2E Tests (2026-03-03)

**Commits:** `5923d18` (Playwright tests), `6d6d401` (seed data), `99141fd` (frontend + E2E)

- Comprehensive frontend dashboard rewrite: 6-tab SPA (Auth, Profile, Accounts, Transfers, Cards, Statements)
- Guided flow rail (6 steps with done/current/pending states)
- Ops/Reviewer panel showing live API request log (method, path, status, latency, X-Request-ID)
- Token stored in memory only (not localStorage), UUID idempotency keys auto-generated
- 5 Playwright E2E tests: dashboard loads, signup flow, login flow, health from browser, ready from browser
- Seed data script (`scripts/seed_data.py`) for demo environment setup
- Used Claude Code experimental agent teams for parallel frontend development

**Iteration:** Initial Playwright tests used generic locators; refined to match actual dashboard HTML structure. SQLite multiprocess threading required isolated `test_e2e.db` with separate server process.

**Tests:** 75 total (70 API + 5 E2E), 94% coverage. **Covers:** 4.10 (enhanced), 4.13 (E2E), 12.1 Playwright gate now passing.

## Challenges and Manual Interventions

| Challenge | Resolution | Manual Decision |
|-----------|------------|----------------|
| passlib crashes on Python 3.13 | Switched to direct `bcrypt` library | Yes — removed passlib dependency entirely |
| JWT refresh tokens identical within same second | Added `jti` (uuid4) claim to payload | Yes — identified via test failure |
| SQLite check-then-act race on balance | Used atomic guarded `UPDATE WHERE balance >= amount` | Yes — per REQUIREMENTS.MD caveat |
| Test isolation | Per-test table create/drop via autouse fixture | Design decision for deterministic tests |

## Evidence Summary

| Metric | Value |
|--------|-------|
| Total tests | 75 (70 API + 5 E2E) |
| Test files | 10 |
| Coverage | 94% (80% minimum) |
| TDD cycles (red→green) | 8 |
| Commits | 16 |
| Lines of app code | ~1200 |
| Lines of test code | ~1100 |
| SLO targets met | 5/5 |
| Security checklist items | 10/10 |
| Release gates passed | 10/10 |
| Traceability rows complete | 12/12 |
| Zero regressions | Verified after every commit |
