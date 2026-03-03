"""Transfer and Transaction ORM models."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.database import Base


def _utcnow():
    return datetime.now(UTC)


def _new_id():
    return str(uuid.uuid4())


class Transfer(Base):
    __tablename__ = "transfers"

    id = Column(String, primary_key=True, default=_new_id)
    source_account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    destination_account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="completed")
    idempotency_key = Column(String, unique=True, nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=_new_id)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    transfer_id = Column(String, ForeignKey("transfers.id"), nullable=True)
    type = Column(String, nullable=False)  # debit, credit, deposit, card_spend
    amount_cents = Column(Integer, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
