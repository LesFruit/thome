"""Card and CardTransaction ORM models."""

import uuid
import secrets
from datetime import datetime, timezone, date
from dateutil.relativedelta import relativedelta

from sqlalchemy import Column, String, Integer, DateTime, Date, ForeignKey

from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


def _new_id():
    return str(uuid.uuid4())


def _generate_card_number():
    """Generate a 16-digit card number (not cryptographically meaningful, demo only)."""
    return "4" + "".join([str(secrets.randbelow(10)) for _ in range(15)])


def _default_expiry():
    return date.today() + relativedelta(years=3)


CARD_STATUS_TRANSITIONS = {
    "active": {"blocked", "cancelled"},
    "blocked": {"active", "cancelled"},
    "cancelled": set(),  # terminal
}


class Card(Base):
    __tablename__ = "cards"

    id = Column(String, primary_key=True, default=_new_id)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    card_number = Column(String, nullable=False, default=_generate_card_number)
    status = Column(String, nullable=False, default="active")
    expiry_date = Column(Date, nullable=False, default=_default_expiry)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class CardTransaction(Base):
    __tablename__ = "card_transactions"

    id = Column(String, primary_key=True, default=_new_id)
    card_id = Column(String, ForeignKey("cards.id"), nullable=False)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    merchant = Column(String, nullable=False)
    idempotency_key = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
