"""Accounts router."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.account import AccountCreateRequest, AccountResponse, AccountUpdateRequest
from app.services import account_service

router = APIRouter(prefix="/api/v1/accounts", tags=["accounts"])


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(
    req: AccountCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return account_service.create_account(db, user, req.account_type)


@router.get("", response_model=list[AccountResponse])
def list_accounts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return account_service.list_accounts(db, user)


@router.get("/{account_id}", response_model=AccountResponse)
def get_account(
    account_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return account_service.get_account(db, user, account_id)


@router.patch("/{account_id}", response_model=AccountResponse)
def update_account(
    account_id: str,
    req: AccountUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return account_service.update_account_status(db, user, account_id, req.status)
