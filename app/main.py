"""FastAPI application factory and lifecycle management."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import init_db, dispose_db
from app.logging_config import setup_logging
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.error_handler import register_error_handlers
from app.routers import health

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    setup_logging(settings.log_level)
    logger.info("Starting %s (env=%s)", settings.app_name, settings.app_env)
    init_db()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down — disposing DB resources")
    dispose_db()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Banking Service API",
    version="0.1.0",
    lifespan=lifespan,
)

# --- Middleware (outermost first) ---
app.add_middleware(RequestIDMiddleware)

# --- Error handlers ---
register_error_handlers(app)

# --- Routers ---
app.include_router(health.router)
