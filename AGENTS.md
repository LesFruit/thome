# Repository Guidelines

## Project Structure & Module Organization
- `app/` contains the FastAPI service.
- `app/routers/` defines HTTP endpoints by domain (`auth`, `accounts`, `cards`, `transfers`, etc.).
- `app/services/` holds business logic; keep routers thin and delegate rules here.
- `app/models/` and `app/schemas/` define SQLAlchemy models and Pydantic contracts.
- `app/middleware/`, `app/auth/`, and `app/config.py` cover cross-cutting concerns.
- `tests/` contains pytest suites (`test_*.py`) plus Playwright E2E coverage.
- `static/` hosts the dashboard UI, `scripts/` contains utility runners, and `docs/` stores evidence/log artifacts.

## Build, Test, and Development Commands
- Start dev server: `uv run uvicorn app.main:app --reload`
- Lint: `uv run --with ruff ruff check app/ tests/`
- Format check: `uv run --with ruff ruff format --check app/ tests/`
- Run API tests with coverage: `uv run --with pytest,httpx,email-validator,pytest-cov pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=80`
- Run Playwright flow tests: `uv run --with pytest,playwright,httpx pytest tests/test_playwright.py -v`
- Docker validation (CI-like): `docker build --target test -t banking-test . && docker run --rm banking-test`

## Coding Style & Naming Conventions
- Target Python 3.11+.
- Ruff is the source of truth for style and linting (`line-length = 100`, import sorting enabled).
- Use `snake_case` for modules, functions, and variables; `PascalCase` for classes.
- Keep endpoint modules domain-focused (`app/routers/cards.py`), and mirror domain tests (`tests/test_cards.py`).
- Prefer explicit types and clear request/response schemas.

## Testing Guidelines
- Framework: `pytest` with FastAPI `TestClient` fixtures from `tests/conftest.py`.
- Naming is enforced by config: files `test_*.py`, functions `test_*`.
- Add or update tests for every behavior change, including error paths and auth/permissions.
- Coverage floor is 80% for `app/`; do not merge below this threshold.

## Commit & Pull Request Guidelines
- Follow Conventional Commit style seen in history: `feat:`, `fix(scope):`, `test:`, `docs:`, `chore:`.
- Keep commits focused and scoped to one change set.
- PRs should include:
  - concise behavior summary and affected endpoints/modules,
  - test evidence (commands run and outcomes),
  - UI proof (screenshot/video) when `static/` or dashboard behavior changes.
- Ensure CI passes lint, tests, and Docker smoke checks before requesting review.

## Security & Configuration Tips
- Copy `.env.example` to `.env`; never commit secrets.
- Set a strong `JWT_SECRET_KEY` outside local development.
- Validate `/health` and `/ready` after deployment changes.
