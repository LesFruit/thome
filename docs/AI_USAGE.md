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

### Session 9: Final Documentation + Test Client (2026-03-03)

Full E2E demo client (13-step flow), updated all docs, security checklist, traceability.

**Tests:** 64 pass. **Covers:** 4.11–4.15 complete.

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
| Total tests | 64 |
| Test files | 7 |
| TDD cycles (red→green) | 8 |
| Commits | 10 |
| Lines of app code | ~1200 |
| Lines of test code | ~600 |
| Zero regressions | Verified after every commit |
