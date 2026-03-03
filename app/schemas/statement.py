"""Pydantic schemas for statements."""

from datetime import date, datetime

from pydantic import BaseModel


class StatementCreateRequest(BaseModel):
    start_date: date
    end_date: date


class StatementResponse(BaseModel):
    id: str
    account_id: str
    start_date: date
    end_date: date
    opening_balance_cents: int
    closing_balance_cents: int
    total_debits_cents: int
    total_credits_cents: int
    transaction_count: int
    created_at: datetime

    model_config = {"from_attributes": True}
