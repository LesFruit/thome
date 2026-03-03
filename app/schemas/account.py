"""Pydantic schemas for holders and accounts."""

from datetime import date, datetime

from pydantic import BaseModel


class HolderCreateRequest(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date


class HolderUpdateRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None


class HolderResponse(BaseModel):
    id: str
    user_id: str
    first_name: str
    last_name: str
    date_of_birth: date
    created_at: datetime

    model_config = {"from_attributes": True}


class AccountCreateRequest(BaseModel):
    account_type: str  # checking, savings


class AccountUpdateRequest(BaseModel):
    status: str  # active, frozen, closed


class AccountResponse(BaseModel):
    id: str
    holder_id: str
    account_type: str
    status: str
    balance_cents: int
    created_at: datetime

    model_config = {"from_attributes": True}
