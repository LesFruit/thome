# Documentation Index (RAG-Graph Style)

## Document Nodes

| ID | Title | Path | Purpose | Owner | Last Verified |
|----|-------|------|---------|-------|---------------|
| D-001 | Requirements Plan | `REQUIREMENTS.MD` | Single-source-of-truth recreation plan | Project | 2026-03-03 |
| D-002 | README | `README.md` | Setup, API reference, project structure | Project | 2026-03-03 |
| D-003 | AI Usage Report | `docs/AI_USAGE.md` | AI-driven development evidence log | Project | 2026-03-03 |
| D-004 | Documentation Index | `docs/INDEX.md` | This file — graph navigation | Project | 2026-03-03 |
| D-005 | Environment Config | `.env.example` | Required env vars and defaults | Platform | 2026-03-03 |
| D-006 | CLAUDE.md | `CLAUDE.md` | AI agent guidance | Platform | 2026-03-03 |
| D-007 | Dockerfile | `Dockerfile` | Multi-stage container build | Platform | 2026-03-03 |
| D-008 | Docker Compose | `docker-compose.yml` | Local dev/runtime parity | Platform | 2026-03-03 |
| D-009 | Test Health | `tests/test_health.py` | Health/readiness probe tests | Test | 2026-03-03 |
| D-010 | Test Middleware | `tests/test_middleware.py` | Request ID, error envelopes | Test | 2026-03-03 |
| D-011 | Test Auth | `tests/test_auth.py` | Auth lifecycle tests (12) | Test | 2026-03-03 |
| D-012 | Test Accounts | `tests/test_holders_accounts.py` | Holder + account tests (13) | Test | 2026-03-03 |
| D-013 | Test Transfers | `tests/test_transfers.py` | Transfer + ledger tests (9) | Test | 2026-03-03 |
| D-014 | Test Cards | `tests/test_cards.py` | Card + spend tests (12) | Test | 2026-03-03 |
| D-015 | Test Statements | `tests/test_statements.py` | Statement tests (5) | Test | 2026-03-03 |
| D-016 | Test Logging | `tests/test_logging_and_health.py` | Logging/sanitization tests (5) | Test | 2026-03-03 |
| D-017 | Demo Client | `scripts/test_client.py` | E2E 13-step demo flow | Test | 2026-03-03 |
| D-018 | Dashboard | `static/index.html` | Frontend UI | Frontend | 2026-03-03 |
| D-019 | Test Stress | `tests/test_stress.py` | Concurrency/stress tests (6) | Test | 2026-03-03 |
| D-020 | CI Pipeline | `.github/workflows/validate.yml` | Lint, test, docker smoke | Platform | 2026-03-03 |
| D-021 | SLO Benchmark | `scripts/benchmark.py` | Latency measurement script | Platform | 2026-03-03 |
| D-022 | Playwright E2E | `tests/test_playwright.py` | Browser E2E tests (5) | Test | 2026-03-03 |
| D-023 | Seed Data | `scripts/seed_data.py` | Demo environment seeder | Test | 2026-03-03 |

## Relationship Edges

| Source | Target | Relationship |
|--------|--------|-------------|
| D-002 | D-001 | depends_on |
| D-003 | D-001 | verified_by |
| D-006 | D-001 | depends_on |
| D-011 | D-001 §4.2 | verified_by |
| D-012 | D-001 §4.3 | verified_by |
| D-013 | D-001 §4.4 | verified_by |
| D-014 | D-001 §4.5 | verified_by |
| D-015 | D-001 §4.6 | verified_by |
| D-016 | D-001 §4.7 | verified_by |
| D-017 | D-001 §10 | verified_by |
| D-018 | D-001 §4.10 | verified_by |
| D-019 | D-001 §5 | verified_by |
| D-020 | D-001 §4.12 | verified_by |
| D-021 | D-001 §13 | verified_by |
| D-022 | D-001 §4.13 | verified_by |
| D-023 | D-001 §10 | verified_by |

## Retrieval Tags

| Tag | Documents |
|-----|-----------|
| `feature` | D-001, D-002 |
| `setup` | D-002, D-005, D-007, D-008 |
| `ai_evidence` | D-003 |
| `test_scope` | D-009–D-019, D-022 |
| `ops_area` | D-005, D-007, D-008, D-016 |
| `layer:auth` | D-011 |
| `layer:domain` | D-012, D-013, D-014, D-015 |
| `layer:platform` | D-009, D-010 |
| `risk:financial` | D-013, D-014, D-019 |
| `risk:security` | D-011, D-016 |
| `ci_pipeline` | D-020 |
| `slo_evidence` | D-021 |
| `layer:e2e` | D-017, D-022, D-023 |

## Start Here

**Implementers:** D-001 → D-006 → D-002 → D-005 → code

**Reviewers:** D-003 → D-001 → D-017 → D-011–D-016 → evidence

**Ops:** D-007 → D-008 → D-005 → D-009 → D-016
