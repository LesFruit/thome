# Multi-stage build for production-ready banking service

# Stage 1: Builder — install Python dependencies
FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml .
RUN pip install --no-cache-dir uv && \
    uv pip compile pyproject.toml -o requirements.txt && \
    uv pip install --system --no-cache -r requirements.txt

# Stage 2: Test — full suite inside Docker
FROM python:3.12-slim AS test

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

# Install test deps
RUN pip install --no-cache-dir pytest pytest-cov httpx email-validator

COPY app/ ./app/
COPY tests/ ./tests/
COPY static/ ./static/
COPY pyproject.toml .

ENV JWT_SECRET_KEY=test-secret-key
CMD ["pytest", "tests/", "-v", "--cov=app", "--cov-report=term-missing", "--cov-fail-under=80"]

# Stage 3: E2E — Playwright-enabled image for browser tests
FROM test AS e2e

RUN pip install --no-cache-dir playwright && \
    python -m playwright install --with-deps chromium

CMD ["pytest", "tests/test_playwright.py", "-v"]

# Stage 4: Runtime — lean image with app code + deps
FROM python:3.12-slim AS runtime

RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy installed packages and binaries from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

# Copy application code + static assets (frontend served by FastAPI)
COPY app/ ./app/
COPY static/ ./static/
COPY pyproject.toml .

# Create data directory for SQLite database
RUN mkdir -p /app/data

RUN chown -R appuser:appuser /app
USER appuser

ENV APP_ENV=production
ENV LOG_LEVEL=INFO
ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
