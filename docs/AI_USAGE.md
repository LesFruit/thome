# AI Usage Report

Tracks AI-driven development decisions, iterations, and evidence.

## Tools

| Tool | Model | Purpose |
|------|-------|---------|
| Claude Code (CLI) | claude-opus-4-6 | Primary development agent |

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

## Evidence

| Metric | Value |
|--------|-------|
| API tests | 70 |
| E2E tests | 2 stories (40+ assertions) |
| Coverage | 94% (80% minimum) |
| TDD cycles | 8 red→green |
| Commits | 20+ |
| SLO targets met | 5/5 |
| Security checklist | 10/10 |
| Release gates | 10/10 |
| Traceability rows | 12/12 |

## Logs

Test execution logs are saved in `docs/logs/`:
- `api-tests.log` — 70 API tests with coverage report (94%)
- `e2e-tests.log` — 2 Playwright E2E story tests
- `backend-e2e-story.log` — 13-step backend flow (signup→logout)
- `lint-report.log` — Ruff lint (all checks passed)
