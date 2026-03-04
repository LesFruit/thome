"""Cards router — issuance, status, spend."""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.card import (
    CardResponse,
    CardSpendRequest,
    CardTransactionResponse,
    CardUpdateRequest,
)
from app.services import card_service

router = APIRouter(prefix="/api/v1", tags=["cards"])


@router.post(
    "/accounts/{account_id}/cards",
    response_model=CardResponse,
    status_code=status.HTTP_201_CREATED,
)
def issue_card(
    account_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return card_service.issue_card(db, user, account_id)


@router.get("/accounts/{account_id}/cards", response_model=list[CardResponse])
def list_cards(
    account_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return card_service.list_cards(db, user, account_id)


@router.get("/cards/{card_id}", response_model=CardResponse)
def get_card(card_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return card_service.get_card(db, user, card_id)


@router.patch("/cards/{card_id}", response_model=CardResponse)
def update_card(
    card_id: str,
    req: CardUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return card_service.update_card_status(db, user, card_id, req.status)


@router.post(
    "/cards/{card_id}/spend",
    response_model=CardTransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def card_spend(
    card_id: str,
    req: CardSpendRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ct, is_new = card_service.card_spend(
        db,
        user,
        card_id,
        req.amount_cents,
        req.merchant,
        req.idempotency_key,
    )
    if not is_new:
        data = CardTransactionResponse.model_validate(ct).model_dump(mode="json")
        return JSONResponse(status_code=200, content=data)
    return ct
