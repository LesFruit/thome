# AI-Driven Development Final Report

## How We Built This Project
We started with **Codex** to convert the assessment brief into a structured execution plan in [`PRD.MD`](./PRD.MD). The PRD defined architecture, acceptance criteria, implementation order, and verification gates for all required modules (auth, holders/accounts, transfers, cards, statements, logging, health checks, containerization, docs).

Implementation was then executed primarily with **Claude Code**, with Codex used for planning, audits, and hardening support.

## AI Workflow (TDD-First)
We used a strict **test-driven AI loop** throughout:
1. Write/extend failing tests for each requirement or edge case.
2. Generate minimal code changes to pass.
3. Run targeted tests, then full regression tests.
4. Commit in small, scoped increments.
5. Log outcomes and manual interventions in [`docs/AI_USAGE.md`](./docs/AI_USAGE.md).

## Cleanup, Audits, and Hardening
After feature completion, we performed periodic cleanup and multi-layer audits (browser, backend, and final comprehensive audit). Final hardening then enforced stricter domain rules:
- Future DOB and blank holder names are now rejected.
- Card status updates are schema-enforced by enum.
- Duplicate statements for the same account/period are blocked at both service and DB-constraint layers.
- Playwright is now supported in Docker via a dedicated `e2e` target.

## Final Validation Results
Latest full validation before submission:
- `uv run --with ruff ruff check app/ tests/` -> **pass**
- `uv run --with ruff ruff format --check app/ tests/` -> **pass**
- `uv run --with pytest,httpx,email-validator,pytest-cov pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=80` -> **229 passed, 3 skipped, 95.16% coverage**
- `uv run --with pytest,playwright,httpx pytest tests/test_playwright.py -v` -> **3 passed**
- `docker run --rm banking-test` -> **229 passed, 3 skipped**
- `docker run --rm banking-e2e` -> **3 passed**
- `docker compose up --build` (no `.env`) -> **service starts and `/health` + `/ready` return success**

## Submission Readiness
- AI usage report updated: [`docs/AI_USAGE.md`](./docs/AI_USAGE.md)
- Final report updated: [`REPORT.MD`](./REPORT.MD)
- Setup/run instructions updated: [`README.md`](./README.md)
- Project is ready for submission.

## Sanitized Delivery Package
We generated a **sanitized zip** from tracked git files only (`git archive`), excluding local/sensitive runtime artifacts such as `.env`, virtual environments, caches, local SQLite test DBs, and `__pycache__` folders.

Yes, the sanitized package still works. After unzip, the receiver should:
1. Run Docker directly with no extra setup: `docker compose up --build` (defaults are built into `docker-compose.yml`).
2. Use `.env` only when overriding defaults from `.env.example` (not required for baseline run).
3. Install dependencies and run via README commands for local non-Docker workflows.
4. Install Playwright browser binaries if running local browser E2E (`playwright install chromium`), or use Docker `e2e` target.
