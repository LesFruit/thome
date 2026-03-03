# Documentation Index

## Document Nodes

| ID | Title | Path | Purpose |
|----|-------|------|---------|
| D-001 | Requirements Plan | `REQUIREMENTS.MD` | Single-source-of-truth implementation plan |
| D-002 | README | `README.md` | Setup, API reference, project structure |
| D-003 | AI Usage Report | `docs/AI_USAGE.md` | AI-driven development evidence log |
| D-004 | Documentation Index | `docs/INDEX.md` | This file |
| D-005 | Environment Config | `.env.example` | Required env vars |
| D-006 | CLAUDE.md | `CLAUDE.md` | AI agent guidance |
| D-007 | Dockerfile | `Dockerfile` | Multi-stage container build |
| D-008 | Docker Compose | `docker-compose.yml` | Local dev/runtime parity |
| D-009 | Test Health | `tests/test_health.py` | Health/readiness probe tests (2) |
| D-010 | Test Middleware | `tests/test_middleware.py` | Request ID, error envelopes (6) |
| D-011 | Test Auth | `tests/test_auth.py` | Auth lifecycle tests (12) |
| D-012 | Test Accounts | `tests/test_holders_accounts.py` | Holder + account tests (13) |
| D-013 | Test Transfers | `tests/test_transfers.py` | Transfer + ledger tests (9) |
| D-014 | Test Cards | `tests/test_cards.py` | Card + spend tests (12) |
| D-015 | Test Statements | `tests/test_statements.py` | Statement tests (5) |
| D-016 | Test Logging | `tests/test_logging_and_health.py` | Logging/sanitization tests (5) |
| D-017 | Demo Client | `scripts/test_client.py` | 13-step E2E backend flow |
| D-018 | Dashboard | `static/index.html` | 7-tab SPA (1300+ lines, dark/light theme, ops panel) |
| D-019 | Test Stress | `tests/test_stress.py` | Concurrency/stress tests (6) |
| D-020 | CI Pipeline | `.github/workflows/validate.yml` | Lint, test, docker smoke |
| D-021 | SLO Benchmark | `scripts/benchmark.py` | Latency measurement |
| D-022 | Playwright E2E | `tests/test_playwright.py` | 2 story-driven E2E tests (40+ assertions) + MP4 video |
| D-023 | Seed Data | `scripts/seed_data.py` | Demo environment seeder |
| D-024 | Demo Recorder | `scripts/record_demo.py` | Records MP4 walkthrough video |
| D-025 | Test Logs | `docs/logs/` | API, E2E, backend story, lint logs |
| D-026 | E2E Video | `docs/videos/playwright-e2e-tests.mp4` | 1920x1080 E2E test recording |
| D-027 | Demo Video | `docs/videos/banking-demo-walkthrough.mp4` | 1920x1080 demo walkthrough |
| D-028 | Browser Audit | `docs/logs/browser-audit.md` | 71-test BrowserOS manual audit (1 bug, 2 findings) |

## Relationship Edges

| Source | Target | Relationship |
|--------|--------|-------------|
| D-003 | D-001 | verified_by |
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
| D-025 | D-003 | evidence_for |
| D-026 | D-022 | evidence_for |
| D-027 | D-024 | evidence_for |
| D-028 | D-001 §4.10 | verified_by |

## Retrieval Tags

| Tag | Documents |
|-----|-----------|
| `test_scope` | D-009–D-019, D-022 |
| `layer:auth` | D-011 |
| `layer:domain` | D-012, D-013, D-014, D-015 |
| `layer:platform` | D-009, D-010, D-020 |
| `layer:e2e` | D-017, D-022, D-025, D-026, D-027 |
| `risk:financial` | D-013, D-014, D-019 |
| `risk:security` | D-011, D-016 |
| `ai_evidence` | D-003, D-025 |
| `video_evidence` | D-026, D-027 |

## Start Here

**Reviewers:** D-003 → D-025 → D-026 → D-001 → D-011–D-016

**Implementers:** D-001 → D-006 → D-002 → code

**Ops:** D-007 → D-008 → D-005 → D-009
