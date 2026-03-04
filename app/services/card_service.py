"""Card business logic — issuance, status, spend with idempotency."""

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.account import Account, AccountHolder
from app.models.card import CARD_STATUS_TRANSITIONS, Card, CardTransaction
from app.models.transaction import Transaction
from app.models.user import User


def _enforce_account_ownership(db: Session, user: User, account_id: str) -> Account:
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    holder = db.query(AccountHolder).filter(AccountHolder.id == account.holder_id).first()
    if not holder or holder.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return account


def _enforce_card_ownership(db: Session, user: User, card_id: str) -> Card:
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    _enforce_account_ownership(db, user, card.account_id)
    return card


def issue_card(db: Session, user: User, account_id: str) -> Card:
    account = _enforce_account_ownership(db, user, account_id)
    if account.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Account is {account.status}",
        )
    card = Card(account_id=account_id)
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


def list_cards(db: Session, user: User, account_id: str) -> list[Card]:
    _enforce_account_ownership(db, user, account_id)
    return db.query(Card).filter(Card.account_id == account_id).all()


def get_card(db: Session, user: User, card_id: str) -> Card:
    return _enforce_card_ownership(db, user, card_id)


def update_card_status(db: Session, user: User, card_id: str, new_status: str) -> Card:
    card = _enforce_card_ownership(db, user, card_id)
    allowed = CARD_STATUS_TRANSITIONS.get(card.status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition card from '{card.status}' to '{new_status}'",
        )
    card.status = new_status
    db.commit()
    db.refresh(card)
    return card


def card_spend(
    db: Session,
    user: User,
    card_id: str,
    amount_cents: int,
    merchant: str,
    idempotency_key: str,
) -> tuple[CardTransaction, bool]:
    """Returns (card_transaction, is_new)."""

    # Idempotency
    existing = (
        db.query(CardTransaction)
        .filter(
            CardTransaction.idempotency_key == idempotency_key,
        )
        .first()
    )
    if existing:
        return existing, False

    card = _enforce_card_ownership(db, user, card_id)

    # Card state check
    if card.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Card is {card.status}",
        )
    if card.expiry_date < date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Card is expired",
        )

    # Account state check
    account = db.query(Account).filter(Account.id == card.account_id).first()
    if account.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Account is {account.status}",
        )

    if amount_cents <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amount must be positive",
        )

    # Atomic guarded debit
    result = db.execute(
        update(Account)
        .where(Account.id == card.account_id)
        .where(Account.balance_cents >= amount_cents)
        .values(balance_cents=Account.balance_cents - amount_cents)
    )
    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient funds",
        )

    ct = CardTransaction(
        card_id=card_id,
        account_id=card.account_id,
        amount_cents=amount_cents,
        merchant=merchant,
        idempotency_key=idempotency_key,
    )
    db.add(ct)

    # Ledger entry
    db.add(
        Transaction(
            account_id=card.account_id,
            type="card_spend",
            amount_cents=amount_cents,
            description=f"Card spend at {merchant}",
        )
    )

    db.commit()
    db.refresh(ct)
    return ct, True
