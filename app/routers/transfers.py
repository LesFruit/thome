"""Transfer and transaction router."""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.schemas.transaction import (
    TransferCreateRequest, TransferResponse,
    DepositRequest, TransactionResponse,
)
from app.schemas.account import AccountResponse
from app.services import transfer_service

router = APIRouter(prefix="/api/v1", tags=["transfers"])


@router.post("/transfers", response_model=TransferResponse, status_code=status.HTTP_201_CREATED)
def create_transfer(
    req: TransferCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    transfer, is_new = transfer_service.create_transfer(
        db, user, req.source_account_id, req.destination_account_id,
        req.amount_cents, req.idempotency_key,
    )
    if not is_new:
        return JSONResponse(status_code=200, content=TransferResponse.model_validate(transfer).model_dump(mode="json"))
    return transfer


@router.get("/transfers", response_model=list[TransferResponse])
def list_transfers(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return transfer_service.list_transfers(db, user)


@router.get("/transfers/{transfer_id}", response_model=TransferResponse)
def get_transfer(
    transfer_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return transfer_service.get_transfer(db, user, transfer_id)


@router.post("/accounts/{account_id}/deposit", response_model=AccountResponse)
def deposit(
    account_id: str,
    req: DepositRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return transfer_service.deposit(db, user, account_id, req.amount_cents)


@router.get("/accounts/{account_id}/transactions", response_model=list[TransactionResponse])
def list_transactions(
    account_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return transfer_service.list_transactions(db, user, account_id)
