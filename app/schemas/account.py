"""Pydantic schemas for holders and accounts."""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, field_validator


class HolderCreateRequest(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date

    @field_validator("first_name", "last_name")
    @classmethod
    def names_must_not_be_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name must not be empty")
        return value

    @field_validator("date_of_birth")
    @classmethod
    def dob_must_not_be_in_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return value


class HolderUpdateRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None

    @field_validator("first_name", "last_name")
    @classmethod
    def update_names_must_not_be_empty(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Name must not be empty")
        return value

    @field_validator("date_of_birth")
    @classmethod
    def update_dob_must_not_be_in_future(cls, value: date | None) -> date | None:
        if value is None:
            return None
        if value > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return value


class HolderResponse(BaseModel):
    id: str
    user_id: str
    first_name: str
    last_name: str
    date_of_birth: date
    created_at: datetime

    model_config = {"from_attributes": True}


class AccountType(StrEnum):
    checking = "checking"
    savings = "savings"


class AccountStatus(StrEnum):
    active = "active"
    frozen = "frozen"
    closed = "closed"


class AccountCreateRequest(BaseModel):
    account_type: AccountType


class AccountUpdateRequest(BaseModel):
    status: AccountStatus


class AccountResponse(BaseModel):
    id: str
    holder_id: str
    account_type: str
    status: str
    balance_cents: int
    created_at: datetime

    model_config = {"from_attributes": True}
