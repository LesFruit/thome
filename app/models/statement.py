"""Statement ORM model."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint

from app.database import Base


def _utcnow():
    return datetime.now(UTC)


def _new_id():
    return str(uuid.uuid4())


class Statement(Base):
    __tablename__ = "statements"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "start_date", "end_date", name="uq_statement_account_period"
        ),
    )

    id = Column(String, primary_key=True, default=_new_id)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    opening_balance_cents = Column(Integer, nullable=False)
    closing_balance_cents = Column(Integer, nullable=False)
    total_debits_cents = Column(Integer, nullable=False)
    total_credits_cents = Column(Integer, nullable=False)
    transaction_count = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
