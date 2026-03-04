# AI Usage Report

Tracks AI-driven development decisions, iterations, and evidence.

## Tools

| Tool | Model | Purpose |
|------|-------|---------|
| Claude Code (CLI) | claude-opus-4-6 | Primary development agent |
| Codex (CLI) | claude-5.3 | Secondary development agent |

## Methodology

**TDD throughout:** write failing tests → implement minimum code → verify zero regressions → commit with requirement reference.

## Development Log

### Session 1: Project Scaffold
`ccff3f8` — Config, database (WAL pragmas), health probes, Dockerfile, test infra.
**2 tests.** Covers: 4.1, 4.8, 4.9, 4.11 (partial).

### Session 2: Middleware
`2ffe7b6` — X-Request-ID, X-Process-Time, error envelopes (no traceback leakage).
**TDD:** 6 tests (5 red → green). **8 total.** Covers: 4.1.

### Session 3: Auth
`f8f7639` — Signup, login, JWT with jti claims, refresh rotation, logout.
**TDD:** 12 tests. Iteration: passlib→bcrypt (Python 3.13 compat), added jti for token uniqueness.
**20 total.** Covers: 4.2.

### Session 4: Holders + Accounts
`fbcdad9` — AccountHolder (KYC), Account (type, status, balance_cents), ownership enforcement, status transitions (active↔frozen→closed).
**TDD:** 13 tests. **33 total.** Covers: 4.3.

### Session 5: Transfers
`673eae4` — Atomic guarded SQL UPDATE (overdraft prevention), double-entry ledger, idempotency keys.
**TDD:** 9 tests. **42 total.** Covers: 4.4.

### Session 6: Cards
`8fd6f2e` — Card state machine (active→blocked/cancelled), card spend with atomic debit, idempotency.
**TDD:** 12 tests. **54 total.** Covers: 4.5.

### Session 7: Statements
`08b43ae` — Period-based balance calculations (opening, in-period totals, closing).
**TDD:** 5 tests. **59 total.** Covers: 4.6.

### Session 8: Logging + Frontend
`c423a59`, `73d9171` — JSON structured logging tests, initial dashboard SPA with guided flow.
**5 logging tests. 64 total.** Covers: 4.7, 4.10.

### Session 9: Documentation
`22400a7` — E2E demo client (13-step flow), README, AI_USAGE, INDEX, CLAUDE.md.
**64 total.** Covers: 4.11.

### Session 10: CI + Stress Tests
`5716e96`, `58c4cc2` — Ruff lint fixes, `.github/workflows/validate.yml` CI pipeline, 6 concurrency/stress tests (overdraft prevention, idempotency under contention, ledger invariants).
**70 tests, 94% coverage.** Covers: 4.12, section 5.

### Session 11: Security + SLO + Traceability
`6fb8bae` — Security validation (secrets scan, auth negatives, log leakage), SLO benchmark (health p95=4.6ms, read p95=9ms, write p95=230ms), traceability matrix (12 rows).
Covers: 4.12–4.15.

### Session 12–13: Frontend Rewrite + Docker + Playwright
`d60e9c6`, `c106f2d`, `73e4519` — Complete frontend rewrite (485 → 1294 lines):
- 7-tab SPA: Auth, Profile, Dashboard, Accounts, Transfers, Cards, Statements
- Visual credit card CSS component, toast notifications, dark/light theme
- Confirmation modals, loading overlay, ops/reviewer panel with API request log
- All 27 API endpoints covered, token in memory only, auto-refresh on 401
- Dockerfile fixes: sh vs bash, missing email-validator dep, SQLite dir
- Playwright E2E tests with 1920x1080 video recording (WebM→MP4 via ffmpeg)
- BrowserOS live demo walkthrough

**Iteration:** Docker build failed 3 times (distinct issues). Sidebar navigation required `showTab()` JS call. Button selectors needed refinement for 1920x1080 resolution.
Covers: 4.9, 4.10, 4.13, 10.5.

### Session 14: Manual Audit + Data Fixes + E2E Rewrite
`2aea36f` — Manual audit revealed bugs that AI generation missed:

1. **Dashboard only loaded 1st account's transactions** — fixed to aggregate all accounts
2. **Card spend/deposit/transfer didn't refresh history tabs** — added `loadTxns()` + `loadAllTransfers()` after every balance-changing operation
3. **Logout didn't reset auth form** — added `showAuthMode('login')` to logout handler
4. **Playwright used wrong DB** — `multiprocessing.Process` inherited parent's `Settings()` singleton; switched to `subprocess.Popen` with explicit env
5. **E2E videos were repetitive** — rewrote 34 fragmented tests → 2 story-driven flows

**72 tests (70 API + 2 E2E stories / 40+ assertions), 94% coverage.**
Covers: 4.10 (bugs fixed), 4.13 (story-driven E2E).

## Challenges and Manual Interventions

| Challenge | Resolution |
|-----------|------------|
| passlib crashes on Python 3.13 | Switched to direct `bcrypt` |
| JWT refresh tokens identical within same second | Added `jti` (uuid4) claim |
| SQLite check-then-act race on balance | Atomic guarded `UPDATE WHERE balance >= amount` |
| Dashboard only showed 1st account activity | Aggregated txns from all accounts |
| Card spend didn't refresh history | Added `loadTxns()` after every balance change |
| Logout left signup form visible | Reset auth mode on logout |
| Playwright used wrong DB via forked singleton | `subprocess.Popen` with explicit env vars |
| E2E videos were repetitive | 2 story-driven flows instead of 34 isolated tests |
| Deposit accepted on frozen/closed accounts | Added account status check to `deposit()` |
| Account closed with non-zero balance | Added balance-zero guard before close transition |
| `account_type` accepted any string | Added `AccountType(StrEnum)` to schema |
| Card issued on frozen/closed account | Added `account.status != "active"` guard to `issue_card()` |
| Empty merchant accepted on card spend | Added `@field_validator("merchant")` to `CardSpendRequest` |

### Session 15: Automated Browser Audit → Backend Bug Discovery
`6d2d042` — 71-test automated browser audit via BrowserOS (Chrome MCP). Drove the frontend through every edge case systematically: auth (8), user journey (18), deposits (4), transfers (7), cards (12), account states (8), cross-user isolation (6), UI/UX (8).

**Key insight: browser-driven testing found 2 backend bugs that 70 unit tests missed.** By exercising the API through actual UI flows (freeze account → try deposit, close account with balance), the audit caught gaps between service boundaries that isolated tests assumed were handled elsewhere.

1. **`deposit()` accepted deposits to frozen/closed accounts** — `transfer_service.py` never checked `account.status`. Transfer service had this guard but deposit didn't. Fixed: `if account.status != "active"` guard.
2. **Account closure succeeded with non-zero balance** — `account_service.py` validated the state transition but not the balance. A user could trap $4000 in an unreachable closed account. Fixed: `if new_status == "closed" and account.balance_cents != 0` guard.

**Cross-user isolation:** 6/6 tests returned HTTP 403 — airtight.
**70 API tests pass, 94% coverage after fixes.**
Covers: 4.3 (account bugs), 4.10 (UI verification).

### Session 16: Schema Validation + Large-Scale Backend Audit
`14b2d87` (schema fix + E2E), this commit (backend audit) — Two-phase audit:

**Phase 1 — Browser API audit (128/129 endpoints pass):**
Systematically hit all 27 API endpoints via BrowserOS JavaScript execution. Found 1 bug: `account_type: "investment"` accepted (HTTP 201 instead of 422). Root cause: `AccountCreateRequest.account_type` was plain `str` with no enum constraint. Fixed with `AccountType(StrEnum)` and `AccountStatus(StrEnum)` in `app/schemas/account.py`. Wrote 58 E2E scenario tests.

**Phase 2 — Pure backend audit (36 tests, 3 more bugs):**
Deep code analysis of all 5 service files, 5 model files, 6 router files to find every untested branch. Created `tests/test_backend_audit.py` with 36 tests across 13 classes. Found and fixed:

1. **Card issued on frozen account (201→400)** — `issue_card()` checked ownership but not account status. Fixed: added `if account.status != "active"` guard in `card_service.py`.
2. **Card issued on closed account (201→400)** — same root cause and fix as above.
3. **Empty merchant accepted on card spend (201→422)** — no validation at schema or service level. Fixed: `@field_validator("merchant")` in `CardSpendRequest` rejects whitespace-only strings.

**Pattern:** Same class of bug as Session 15 (missing status checks at service boundaries). Browser + backend audit combo catches gaps that isolated unit tests miss.

**158 tests (94 API + 58 E2E + 6 stress), 95% coverage.** All lint clean.
Covers: 4.3, 4.4, 4.5 (bugs fixed), 4.13 (E2E scenarios).

### Session 17: Final Comprehensive Audit (61 tests)
Exhaustive edge-case sweep covering remaining untested paths. Mapped all 27 endpoints, service guards, state transitions, and error conditions. Added `tests/test_final_audit.py` with 61 tests across 25 classes.

Checkpoint outcomes:
- 0 critical defects found in core financial/security flows
- 225-test suite checkpoint reached with 95.70% coverage
- Two design-level policy gaps were explicitly documented for follow-up:
  - future DOB acceptance
  - duplicate statements for same account/period

### Session 18: Hardening Pass + Playwright Docker Parity (Final Submission Prep)
Post-audit hardening focused on turning documented design gaps into enforced policy and tightening test/runtime parity.

**Changes implemented:**
1. **Holder schema hardening** (`app/schemas/account.py`)
   - reject future DOB
   - reject blank/whitespace first/last names
2. **Card status schema hardening** (`app/schemas/card.py`)
   - `CardUpdateRequest.status` moved from free-form `str` to enum (`active|blocked|cancelled`)
3. **Statement duplicate prevention** (`app/services/statement_service.py`, `app/models/statement.py`)
   - service-level duplicate-period check returns HTTP 409
   - DB-level unique constraint on `(account_id, start_date, end_date)` for atomic protection
   - integrity error handling mapped to consistent HTTP 409 response
4. **Playwright operational parity**
   - added Docker `e2e` stage with Playwright + Chromium install
   - verified `docker run banking-e2e` executes E2E suite successfully
5. **Repository hygiene**
   - ran `ruff format app/ tests/` and re-validated lint
   - updated README setup/test commands (local + Docker E2E path)
   - refreshed report docs for submission readiness

**Tests added/updated (TDD loop):**
- `tests/test_holders_accounts.py`: future DOB + empty name rejection
- `tests/test_cards.py`: invalid card status rejected at schema layer (422)
- `tests/test_statements.py`: duplicate statement period rejected (409)
- `tests/test_final_audit.py`: expectations updated for hardened behavior

**Validation results (latest):**
- `uv run --with ruff ruff check app/ tests/` → pass
- `uv run --with ruff ruff format --check app/ tests/` → pass
- `uv run --with pytest,httpx,email-validator,pytest-cov pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=80` → **229 passed, 3 skipped, 95.16% coverage**
- `uv run --with pytest,playwright,httpx pytest tests/test_playwright.py -v` → **3 passed**
- `docker run --rm banking-test` → **229 passed, 3 skipped**
- `docker run --rm banking-e2e` → **3 passed**

## Evidence

| Metric | Value |
|--------|-------|
| Full suite (default env) | 229 passed, 3 skipped |
| Playwright E2E | 3/3 passed (local and Docker `e2e` target) |
| Coverage | 95.16% (80% minimum) |
| TDD cycles | 8 red→green |
| Commits | 30+ |
| SLO targets met | 5/5 |
| Security checklist | 10/10 |
| Release gates | 10/10 |
| Browser audit | 128/129 endpoints pass (1 schema bug fixed) |
| Backend audit | 36 tests (3 bugs fixed) |
| Final audit | 61 tests (0 bugs — all edge cases pass) |
| Traceability rows | 12/12 |

## Logs

Test execution logs are saved in `docs/logs/`:
- `api-tests-225.log` — 225 API tests with coverage report (95.70%)
- `e2e-tests.log` — 2 Playwright E2E story tests
- `backend-e2e-story.log` — 13-step backend flow (signup→logout)
- `lint-report.log` — Ruff lint (all checks passed)
- `browser-audit.md` — 71-test BrowserOS manual audit (1 bug fixed, 2 design findings)

Latest hardening verification was run directly from CLI/Docker and is summarized in Session 18.
