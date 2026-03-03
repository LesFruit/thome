"""Pydantic schemas for transfers and transactions."""

from datetime import datetime

from pydantic import BaseModel


class TransferCreateRequest(BaseModel):
    source_account_id: str
    destination_account_id: str
    amount_cents: int
    idempotency_key: str


class TransferResponse(BaseModel):
    id: str
    source_account_id: str
    destination_account_id: str
    amount_cents: int
    status: str
    idempotency_key: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DepositRequest(BaseModel):
    amount_cents: int


class TransactionResponse(BaseModel):
    id: str
    account_id: str
    transfer_id: str | None
    type: str
    amount_cents: int
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
