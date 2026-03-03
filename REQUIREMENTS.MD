# Recreation Implementation Plan (AI-Driven, Production-Ready Banking Service)

This document is a detailed execution plan to recreate the project against the stated assessment requirements.
It is the single-source-of-truth recreation document and includes embedded operational checklists/templates.

Primary objectives:
- Deliver all required banking capabilities end-to-end.
- Demonstrate production readiness through operational controls and verification.
- Demonstrate effective AI-driven development with traceable evidence, not claims.

---

## 1) Requirement Baseline (From Assessment)

### Core components
- Service interface:
  - Signing up
  - Authentication
  - Account Holders
  - Accounts
  - Transactions
  - Money Transfer
  - Cards
  - Statements
- Database:
  - SQLite implementation
- Test suite:
  - Comprehensive critical coverage
  - Unit tests for business logic
  - Integration tests for API endpoints
- Containerization:
  - Dockerfile
  - docker-compose
  - environment variable configuration
  - multi-stage build (bonus)
- Logging and monitoring:
  - structured logging
  - log levels and formatting
  - error tracking/reporting
- Health checks:
  - health endpoint
  - DB connectivity checks
  - readiness probe
  - graceful shutdown

### Deliverables
- Source code
- Documentation
- AI usage report
- RAG-graph style documentation index
- Security validation checklist
- Demo evidence pack
- Operational runbooks
- Release checklist
- SLO/SLI definition with latency and speed tracking
- Single canonical recreation plan with embedded execution templates
- Bonus items (test client + simple frontend)

### Working style constraints
- Commit regularly with meaningful messages.
- Include AI usage log in Markdown.
- No committed secrets.
- Production readiness is a key judging dimension.

---

## 2) System Design Blueprint

### Backend architecture
- Framework: FastAPI
- Pattern: strict layering
  - `app/middleware/`: cross-cutting platform concerns
  - `app/routers/`: HTTP contract and request parsing only
  - `app/services/`: business rules and invariants
  - `app/models/`: SQLAlchemy ORM persistence
  - `app/schemas/`: Pydantic contracts
  - `app/auth/`: auth primitives and dependencies
  - `app/database.py`: engine/session lifecycle and SQLite pragmas

### Data model and financial invariants
- Monetary values are integer cents only (`*_cents`).
- Transfer writes are double-entry (debit + credit transaction records).
- Overdraft prevention uses atomic guarded SQL updates.
- Idempotency keys protect retryable write paths.
- Ownership is validated in service layer on every protected resource.

### Operational design
- JSON structured logs to stdout.
- Correlation via `X-Request-ID` + request context.
- Error envelopes are consistent and safe.
- `/health` for liveness, `/ready` for DB-backed readiness.
- Graceful shutdown disposes DB resources.

### Frontend design direction
- Single dashboard application.
- Two modes in same UI:
  - User View (functional banking operations)
  - Reviewer/Ops View (read-only operational evidence)
- Guided flow rail:
  1. Signup/Login
  2. Create Holder
  3. Open Account
  4. Transfer
  5. Card Spend
  6. Generate Statement
  7. Refresh/Logout

Rationale: this demonstrates both business capabilities and operational maturity without unnecessary admin scope.

---

## 3) Tooling and Development Workflow

### Build/run/test tools
- `uv` for Python execution and dependency tooling.
- `pytest` + `pytest-cov` for API tests and coverage.
- `playwright` + `pytest` for browser E2E.
- `ruff` for lint and formatting.
- `docker` + `docker compose` for container runtime validation.

### AI workflow (required for assessment strength)
- Use AI in a verification-gated loop:
  1. Prompt from explicit requirement and invariant.
  2. Generate small, layer-scoped diff.
  3. Run targeted tests immediately.
  4. Run broader suite before integration.
  5. Record prompt/outcome/manual judgment in `docs/AI_USAGE.md`.

### Evidence discipline
- Every significant AI-generated change must link to:
  - requirement it satisfies
  - tests that validate it
  - caveat/risk considered
  - manual intervention if applicable

---

## 4) Implementation Workstreams

## 4.1 Platform Foundation
- Initialize project structure and app factory.
- Configure settings (`.env` + defaults + safety warning behavior).
- Configure SQLite engine/session and pragmas.
- Wire middleware stack and exception handlers.
- Add health and readiness routers.

Acceptance criteria:
- App boots locally and via container.
- `/health` and `/ready` return expected shape.
- DB session lifecycle is clean in startup/shutdown.

Key caveats:
- SQLite defaults are unsafe for production-like concurrency unless pragmas are set.
- Middleware order affects behavior and logging consistency.

## 4.2 Auth and Identity
- Implement signup/login/refresh/logout endpoints.
- Password hashing with bcrypt.
- Refresh token hashing + rotation/revocation.
- Access-token dependency for protected routes.

Acceptance criteria:
- Invalid credentials return generic auth failure.
- Refresh flow rotates token and invalidates old token.
- Protected endpoints reject invalid, expired, revoked, or inactive identity.

Key caveats:
- Auth errors must not leak internals.
- Token lifecycle edge cases are easy to miss without targeted tests.

## 4.3 Account Holder and Account Domains
- Create/read/update account holder profile (KYC fields).
- Account create/list/get/update status.
- Enforce account status transition rules.

Acceptance criteria:
- One holder per user profile path works end-to-end.
- Account types and status transitions are validated.
- Ownership enforcement prevents cross-user access.

Key caveats:
- Status transition bugs cascade into transfer/card failures.

## 4.4 Transfers and Transactions
- Implement transfer create/list/get.
- Enforce self-transfer/insufficient-funds/status rules.
- Implement idempotency handling at app + DB constraint level.
- Write transfer-related ledger entries (double-entry).
- Implement transaction list/get with filtering/pagination.

Acceptance criteria:
- Transfer retries with same key do not double-debit.
- Double-entry invariant holds under concurrency tests.
- Listing/filtering/pagination behave consistently.

Key caveats:
- Check-then-act debit logic is race-prone and must be replaced by atomic guarded update.

## 4.5 Cards and Card Transactions
- Issue/list/get/update card states.
- Implement card spend create/list/get.
- Enforce card/account state validation (blocked/cancelled/expired/frozen/closed).
- Idempotent card spend behavior.

Acceptance criteria:
- Card spend updates account balance and ledger as expected.
- Idempotency key replay returns prior result safely.
- Cross-user card operations are denied.

Key caveats:
- Card and account state machines must both gate spending.

## 4.6 Statements
- Generate/list/get statement by account and period.
- Compute opening/closing balance, debit/credit totals, count.

Acceptance criteria:
- Statement totals reconcile with account transactions in period.
- Unauthorized statement access is denied.

Key caveats:
- Period boundary handling must be deterministic and test-covered.

## 4.7 Logging, Monitoring, and Error Tracking
- JSON log formatter and configurable log levels.
- Access logs with method, route-template path, status, duration.
- Error tracking via unified error handler.
- Sanitized behavior:
  - no sensitive operational fields in event logs
  - no raw path IDs in access logs
  - no sensitive traceback leakage in responses

Acceptance criteria:
- Structured log fields present and parseable.
- Log sanitization tests pass.
- Error envelope consistency verified.

Key caveats:
- Observability can create compliance risk if logs capture sensitive identifiers.

## 4.8 Health and Lifecycle
- Liveness endpoint independent of DB.
- Readiness endpoint validates DB connectivity.
- Graceful shutdown disposes DB engine/resources.

Acceptance criteria:
- Readiness returns failure signal when DB check fails.
- Shutdown path executes cleanly in container and tests.

Key caveats:
- A green liveness probe does not imply service readiness.

## 4.9 Containerization and Environment Configuration
- Create Dockerfile with production-safe defaults.
- Include `HEALTHCHECK`.
- Run as non-root user.
- Build with dependency strategy optimized for reproducibility.
- Provide `docker-compose.yml` for local dev/runtime parity.
- Provide `.env.example` with required keys and placeholders.
- Implement multi-stage Docker build (bonus, recommended).

Acceptance criteria:
- `docker compose up --build` starts API and dashboard reliably.
- `/health` and `/ready` pass in running container.
- Env vars documented and consumed by config.
- No secrets are committed.

Key caveats:
- Local process success is not equivalent to containerized success.
- Environment mismatch is a common source of hidden failures.

## 4.10 Frontend and Demonstration Flow
- Build simple frontend dashboard with required functional tabs.
- Add guided flow panel and step-by-step action states.
- Add Reviewer/Ops drawer with request ID, latency, response status, and sanitized req/resp preview.

Acceptance criteria:
- Full user journey is executable from UI.
- Frontend failures surface backend error envelope clearly.
- Reviewer can see operational evidence without inspecting server logs manually.

Key caveats:
- Do not build full admin feature set unless backed by role model in API.

## 4.11 Documentation and Reporting
- README with setup/API/deployment instructions.
- Security considerations document.
- Future roadmap document.
- Docker deployment instructions.
- RAG-graph style documentation index in `docs/INDEX.md`:
  - document nodes (title, path, purpose, owner)
  - relationship edges (depends_on, verified_by, supersedes, related_to)
  - retrieval tags (`feature`, `layer`, `risk`, `test_scope`, `ops_area`)
  - "start here" reading paths for implementers and reviewers
- AI usage report with prompts/iterations/challenges/manual decisions.
- PRD compliance matrix with evidence mapping.
- Final report emphasizing production readiness + AI-driven execution quality.

Acceptance criteria:
- Documentation matches actual implementation and test outcomes.
- Reviewer can reproduce the system with documented commands only.
- A reviewer can traverse requirement -> design -> code -> tests -> evidence using the index graph.

Key caveats:
- Docs that describe intended behavior but not observed behavior fail credibility.
- A static list of docs without relationships is weak for AI retrieval and reviewer navigation.

## 4.12 CI/CD and Branching Strategy
- Use short-lived feature branches with clear scope and ownership.
- Enforce automated pull-request gates:
  - lint/format
  - API tests
  - frontend E2E
  - stress tests (or scheduled nightly if runtime-heavy)
- Require reviewer approval for release-bound changes.
- Tag release candidates and attach gate evidence artifacts.

Acceptance criteria:
- Every release-bound PR has automated checks recorded.
- Failing required checks block merge.
- Release tags map to checklist and SLO snapshot records.

Key caveats:
- Manual-only verification does not scale and misses regressions.

## 4.13 Data Durability, Backup, and Recovery
- Define SQLite persistence path and Docker volume strategy.
- Define backup cadence and retention policy per environment.
- Define restore drill procedure and recovery verification steps.
- Document expected blast radius for data loss scenarios.

Acceptance criteria:
- Backup and restore procedure is documented and executable.
- Restore validation includes readiness checks and critical flow smoke tests.

Key caveats:
- WAL mode improves concurrency but is not a substitute for backups.

## 4.14 API Contract and Versioning
- Keep routes versioned under `/api/v1/...`.
- Maintain consistent response envelopes for success and error paths.
- Track breaking/non-breaking API changes in release notes.
- Add contract assertions in integration/E2E tests for critical schemas.

Acceptance criteria:
- Public API behavior is predictable and versioned.
- Contract regressions are caught by tests before release.

Key caveats:
- Silent contract drift breaks frontend and reviewer demos quickly.

## 4.15 Performance Benchmarking Harness
- Define repeatable benchmark scenarios:
  - health/readiness
  - account list/get
  - transfer create
  - card spend create
- Capture throughput and latency percentiles per scenario.
- Store benchmark snapshots with commit hash and environment label.

Acceptance criteria:
- Each release candidate includes benchmark snapshot evidence.
- Latency/throughput regressions are visible and triaged.

Key caveats:
- Comparing metrics across mismatched environments leads to false conclusions.

---

## 5) Test Strategy and Coverage Plan

### Unit tests (service layer)
- Validate business rules independently from HTTP transport.
- Focus: auth lifecycle, transfer rules, card rules, statement calculations.

### Integration tests (router/API)
- Validate request/response contracts, validation, auth enforcement, error envelopes.
- Include ownership checks and status transition failures.

### E2E flow tests (API)
- Full journey:
  - signup -> holder -> account -> transfer -> transaction verify -> card -> statement -> logout

### E2E edge cases
- Insufficient funds
- Self-transfer
- Frozen/closed account operations
- Blocked/cancelled/expired card
- Duplicate idempotency-key replay
- Cross-user access denial
- Refresh/revoked token failures
- Readiness failure behavior

### Frontend E2E (Playwright)
- Happy path flow through dashboard tabs.
- Form validation and error rendering.
- Unauthorized and failure-state behavior.

### Stress/concurrency tests
- Concurrent transfer attempts on shared balance.
- Idempotency under concurrency.
- Ledger invariant checks under load.

Acceptance criteria:
- Critical-path tests pass consistently.
- Regression tests exist for each high-risk bug fixed during implementation.

---

## 6) Quality Gates and Verification Commands

```bash
# Lint / format
uv run ruff check app/ tests/
uv run ruff format app/ tests/

# API test suite + coverage
uv run --with pytest,httpx,pytest-cov pytest tests/ -v --ignore=tests/test_playwright.py --cov=app --cov-report=term-missing

# Browser E2E suite
uv run --with pytest,playwright,httpx pytest tests/test_playwright.py -v

# End-to-end demo client
uv run scripts/test_client.py

# Container runtime verification
docker compose up --build
```

Container smoke checks:
- `GET /health` returns healthy response.
- `GET /ready` returns ready (or unavailable on forced DB failure).
- `/dashboard/` loads.
- Shutdown path logs clean resource disposal.

---

## 7) AI-Driven Development Evidence Plan

Capture in `docs/AI_USAGE.md`:
- Tools and models used.
- Representative prompts with intent.
- Iteration log:
  - what AI produced
  - what failed in tests/review
  - what was corrected
- Challenges and how AI accelerated resolution.
- Explicit manual intervention decisions and rationale.

Store raw execution transcripts in `docs/logs/`.
Keep the RAG-graph index updated when adding/changing docs.

Acceptance criteria:
- A reviewer can trace key decisions from prompt -> code -> test -> outcome.
- AI/reviewer retrieval paths remain accurate after each major change.

---

## 8) Risk Register and Caveats

1. SQLite concurrency limits
- Mitigation: WAL + atomic guarded updates + stress tests.

2. Idempotency race windows
- Mitigation: app-layer lookup + DB uniqueness + IntegrityError reconciliation.

3. Sensitive data leakage via logs
- Mitigation: sanitize paths/events/errors; regression tests for log safety.

4. Over-scoping frontend/admin features
- Mitigation: keep to required user flows + read-only reviewer evidence panel.

5. AI overconfidence and unverifiable output
- Mitigation: verification-gated loop and strict evidence mapping.

6. Environment/config drift
- Mitigation: `.env.example`, explicit config docs, Docker parity checks.

---

## 9) Embedded Security Validation Checklist (Required)

This is the canonical checklist. Do not maintain a separate mirror document.

### 9.1 Secrets and Sensitive Data Scan
- [ ] No secrets in tracked files.
- [ ] `.env` and DB artifacts are excluded from VCS.
- [ ] Demo credentials are explicitly non-production.

Suggested commands:
```bash
git ls-files | rg -n "(.env|\\.db$|banking\\.db)" || true
rg -n "(api[_-]?key|secret|token|password\\s*=|BEGIN PRIVATE KEY|AWS_SECRET|JWT_SECRET_KEY=)" . --glob '!.git' --glob '!*.lock'
```

### 9.2 Auth Negative Validation
- [ ] Invalid credentials rejected.
- [ ] Expired/revoked refresh token rejected.
- [ ] Inactive user blocked.
- [ ] Cross-user resource access denied.

Suggested commands:
```bash
uv run --with pytest,httpx pytest tests/test_auth.py -v
uv run --with pytest,httpx pytest tests/test_error_codes.py -v
```

### 9.3 Log Leakage Assertions
- [ ] Access logs do not expose raw resource IDs when avoidable.
- [ ] Financial event completion logs are redacted/safe.
- [ ] 500 responses do not leak stack traces or sensitive internals.

Suggested commands:
```bash
uv run --with pytest,httpx pytest tests/test_logging_and_health.py -v
```

### 9.4 Dependency Audit Cadence
- Weekly dependency review.
- Monthly full vulnerability audit.
- Immediate triage for new critical/high advisories.

Acceptance criteria:
- Checklist executed pre-release with attached evidence.
- Security-relevant tests pass in CI.

Key caveats:
- Controls without repeatable execution degrade quickly.

---

## 10) Embedded Demo Evidence Pack (Reviewer Bundle)

This is the canonical reviewer bundle template. Do not maintain a separate mirror document.

### 10.1 Environment Snapshot
- Date:
- Commit hash:
- Runtime (python/docker/os):

### 10.2 Exact Command Set
```bash
uv run uvicorn app.main:app --reload
uv run scripts/seed_data.py
uv run scripts/test_client.py
uv run --with pytest,httpx,pytest-cov pytest tests/ -v --ignore=tests/test_playwright.py --cov=app --cov-report=term-missing
uv run --with pytest,playwright,httpx pytest tests/test_playwright.py -v
docker compose up --build
```

### 10.3 Expected Output Matrix
| Scenario | Command / Action | Expected Result |
|----------|------------------|-----------------|
| Liveness | `GET /health` | `status=healthy` |
| Readiness | `GET /ready` | `status=ready` (or controlled `unavailable` on DB fault) |
| API flow | `scripts/test_client.py` | End-to-end flow completes |
| UI flow | Playwright suite | Core dashboard flow passes |

### 10.4 Edge-Case Evidence
- [ ] insufficient funds
- [ ] duplicate idempotency replay
- [ ] cross-user denial
- [ ] blocked/cancelled/expired card handling
- [ ] readiness failure handling

For each edge case, attach:
- request/command
- expected status code and error code
- output/screenshot evidence

### 10.5 Screenshot Inventory
- [ ] accounts/transfers/cards/statements/profile views
- [ ] guided flow progression
- [ ] reviewer/ops evidence view (request_id, status, latency)
- [ ] representative failure state in UI

Acceptance criteria:
- Reviewer can reproduce outcomes from commands only.
- Evidence is timestamped and tied to commit hash.

Key caveats:
- Non-deterministic demos are low-signal for reviewers.

---

## 11) Embedded Runbook Matrix (Operational Procedures)

This section is the canonical runbook summary. Do not maintain separate mirror runbook files.

| Incident Class | Detection | First Response | Primary Diagnostics | Escalate When |
|----------------|-----------|----------------|---------------------|---------------|
| Incident triage | 5xx spike, latency spike, readiness failures | check health/ready, capture logs | `docker compose logs api --tail=200` | unresolved after one full cycle |
| DB contention | lock/busy symptoms, write latency spikes | reduce write pressure, preserve logs | stress test + log grep for lock/busy | recurring after mitigation |
| Rate limit issues | elevated 429 on normal usage | validate traffic legitimacy | inspect rate-limit/error logs | abuse vs UX conflict unresolved |
| Readiness failures | `/ready` unstable/unavailable | keep out of rotation | health/ready checks + config/log review | recurring oscillation |
| Token/revocation issues | abnormal auth refresh failures | scope impact and preserve evidence | auth/error test runs + log scan | cross-client persistent failure |

Runbook content requirements:
- symptoms
- containment
- diagnosis commands
- remediation
- recovery verification
- escalation rules

Acceptance criteria:
- On-call style response can be executed from docs without tribal knowledge.

Key caveats:
- Runbooks not exercised become stale and misleading.

---

## 12) Embedded Release Checklist (Pre-Release Gates)

This is the canonical release gate list. Do not maintain a separate mirror document.

### 12.1 Required Gates
- [ ] `ruff check` passes
- [ ] formatting applied/clean
- [ ] API suite passes (unit/integration/e2e)
- [ ] stress/concurrency suite passes
- [ ] Playwright suite passes
- [ ] docker build + compose smoke checks pass
- [ ] security validation checklist executed
- [ ] RAG index and docs refreshed
- [ ] demo evidence bundle updated
- [ ] SLO/SLI snapshot recorded

### 12.2 Release Record
- Release version/tag:
- Commit hash:
- Date:
- Release owner:
- Approvers:
- Risks/notes:

Acceptance criteria:
- No release proceeds with unchecked required gates.
- Evidence includes owner + date + commit hash.

Key caveats:
- Checkbox-only signoff without artifacts is not sufficient.

---

## 13) Embedded SLO/SLI and Performance Tracking (Speed + Latency)

This section is the canonical performance baseline. Do not maintain a separate mirror document.

### 13.1 SLO Targets
| Area | Target | Window |
|------|--------|--------|
| Availability | >= 99.9% | rolling 30 days |
| Read latency | p95 <= 200ms | daily + per release |
| Write latency | p95 <= 350ms | daily + per release |
| Health latency | p95 <= 50ms | daily + per release |
| Error rate (5xx) | <= 1% | daily |

### 13.2 SLI Signals to Track
- request count
- throughput (req/s)
- latency percentiles (p50/p95/p99)
- 5xx error rate
- endpoint-level latency distribution
- readiness success rate

### 13.3 Measurement Cadence
- Per PR: collect test durations + smoke latency snapshot.
- Per release candidate: collect percentile/throughput snapshot.
- Weekly: review trend drift and open remediation actions.

### 13.4 Trend Table Template
| Date | Commit | Env | Requests | Throughput (req/s) | p50 | p95 | p99 | 5xx Rate | Notes |
|------|--------|-----|----------|--------------------|-----|-----|-----|----------|-------|
| YYYY-MM-DD | `<hash>` | local-docker | | | | | | | |

### 13.5 Trigger Conditions
- p95/p99 increase > 20% vs previous release.
- 5xx rate exceeds target.
- readiness failures recur.

Acceptance criteria:
- Each release candidate includes a filled snapshot row.
- Any SLO miss has remediation notes and owner.

Key caveats:
- Compare only within equivalent environment classes.

---

## 14) Ownership and Execution Cadence

Recommended ownership model:
- Platform owner: middleware, logging, health, container/runtime.
- Domain owner: transfers/cards/statements invariants and service behavior.
- Test owner: quality gates, CI health, regression portfolio.
- Docs owner: RAG index, evidence freshness, release artifacts.

Cadence:
- Daily: feature/test progress + blocker log.
- Per merge candidate: targeted tests + quick smoke.
- Per release candidate: full gates + demo evidence + SLO snapshot.

Acceptance criteria:
- Every critical artifact has an owner and last-verified date.
- Gate failures are assigned and tracked to closure.

---

## 15) Embedded Traceability Matrix Template

Use this table for requirement-level auditability.

| Req ID | Requirement | Design Section | Code Paths | Test Coverage | Evidence Artifact | Owner | Status |
|--------|-------------|----------------|------------|---------------|-------------------|-------|--------|
| 1.x | Service Interface | Section 2 + 4.x | `app/routers/*`, `app/services/*` | unit + integration + e2e | demo pack + test runs |  |  |
| 2.x | SQLite DB | Section 2 + 4.1 + 4.13 | `app/database.py`, `app/models/*` | integration + stress | logs + readiness + stress |  |  |
| 3.x | Test suite | Section 5 | `tests/*` | all layers | pytest reports |  |  |
| 4.x | Containerization | Section 4.9 | `Dockerfile`, `docker-compose.yml` | smoke + readiness | docker logs/screenshots |  |  |
| 5.x | Logging/Monitoring | Section 4.7 | `app/logging_config.py`, middleware | logging tests | sanitized log evidence |  |  |
| 6.x | Health checks | Section 4.8 | `app/routers/health.py` | health/readiness tests | probe outputs |  |  |
| 7.x | Documentation | Section 4.11 | `README.md`, `docs/*` | doc review gate | index + report artifacts |  |  |

Acceptance criteria:
- Every requirement row has concrete code, tests, and evidence links.
- No release proceeds with incomplete traceability for required items.

---

## 16) Definition of Done

Project recreation is complete only when all are true:
- Required service components are implemented and verified.
- SQLite-backed domain behavior satisfies financial invariants.
- Tests cover unit, integration, API E2E, frontend E2E, and concurrency risk.
- Docker requirements are implemented and validated.
- Logging/monitoring/health/lifecycle behaviors are production-ready.
- Security checklist, release checklist, runbooks, demo evidence pack, and SLO/SLI docs are complete and current.
- Traceability matrix is complete for all required assessment components.
- Documentation and AI usage evidence are complete and internally consistent.
- No secrets are committed.
