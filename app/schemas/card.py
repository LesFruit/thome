"""Pydantic schemas for cards."""

from datetime import date, datetime

from pydantic import BaseModel


class CardResponse(BaseModel):
    id: str
    account_id: str
    card_number: str
    status: str
    expiry_date: date
    created_at: datetime

    model_config = {"from_attributes": True}


class CardUpdateRequest(BaseModel):
    status: str


class CardSpendRequest(BaseModel):
    amount_cents: int
    merchant: str
    idempotency_key: str


class CardTransactionResponse(BaseModel):
    id: str
    card_id: str
    account_id: str
    amount_cents: int
    merchant: str
    idempotency_key: str
    created_at: datetime

    model_config = {"from_attributes": True}
