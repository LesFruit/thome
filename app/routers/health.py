"""Health and readiness probe endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    """Liveness probe — independent of DB."""
    return {"status": "healthy"}


@router.get("/ready")
def ready(db: Session = Depends(get_db)):
    """Readiness probe — validates DB connectivity."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        return {"status": "unavailable"}, 503
