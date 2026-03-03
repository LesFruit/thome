"""Statements router."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.statement import StatementCreateRequest, StatementResponse
from app.services import statement_service

router = APIRouter(prefix="/api/v1", tags=["statements"])


@router.post(
    "/accounts/{account_id}/statements",
    response_model=StatementResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_statement(
    account_id: str,
    req: StatementCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return statement_service.generate_statement(db, user, account_id, req.start_date, req.end_date)


@router.get("/accounts/{account_id}/statements", response_model=list[StatementResponse])
def list_statements(
    account_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return statement_service.list_statements(db, user, account_id)


@router.get("/statements/{statement_id}", response_model=StatementResponse)
def get_statement(
    statement_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return statement_service.get_statement(db, user, statement_id)
