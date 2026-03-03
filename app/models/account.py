"""AccountHolder and Account ORM models."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


def _utcnow():
    return datetime.now(UTC)


def _new_id():
    return str(uuid.uuid4())


# Valid status transitions
ACCOUNT_STATUS_TRANSITIONS = {
    "active": {"frozen", "closed"},
    "frozen": {"active", "closed"},
    "closed": set(),  # terminal state
}


class AccountHolder(Base):
    __tablename__ = "account_holders"

    id = Column(String, primary_key=True, default=_new_id)
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    date_of_birth = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    accounts = relationship("Account", back_populates="holder", cascade="all, delete-orphan")


class Account(Base):
    __tablename__ = "accounts"

    id = Column(String, primary_key=True, default=_new_id)
    holder_id = Column(String, ForeignKey("account_holders.id"), nullable=False)
    account_type = Column(String, nullable=False)  # checking, savings
    status = Column(String, nullable=False, default="active")
    balance_cents = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    holder = relationship("AccountHolder", back_populates="accounts")
