"""Statement business logic — generate, list, get with period calculations."""

from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.account import Account, AccountHolder
from app.models.statement import Statement
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


def generate_statement(
    db: Session, user: User, account_id: str, start_date: date, end_date: date,
) -> Statement:
    _enforce_account_ownership(db, user, account_id)

    start_dt = datetime(start_date.year, start_date.month, start_date.day, tzinfo=timezone.utc)
    end_dt = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59, tzinfo=timezone.utc)

    # Transactions before the period (for opening balance)
    pre_txns = db.query(Transaction).filter(
        Transaction.account_id == account_id,
        Transaction.created_at < start_dt,
    ).all()

    opening_balance = 0
    for t in pre_txns:
        if t.type in ("credit", "deposit"):
            opening_balance += t.amount_cents
        elif t.type in ("debit", "card_spend"):
            opening_balance -= t.amount_cents

    # Transactions in the period
    period_txns = db.query(Transaction).filter(
        Transaction.account_id == account_id,
        Transaction.created_at >= start_dt,
        Transaction.created_at <= end_dt,
    ).all()

    total_debits = sum(t.amount_cents for t in period_txns if t.type in ("debit", "card_spend"))
    total_credits = sum(t.amount_cents for t in period_txns if t.type in ("credit", "deposit"))
    closing_balance = opening_balance + total_credits - total_debits

    stmt = Statement(
        account_id=account_id,
        start_date=start_date,
        end_date=end_date,
        opening_balance_cents=opening_balance,
        closing_balance_cents=closing_balance,
        total_debits_cents=total_debits,
        total_credits_cents=total_credits,
        transaction_count=len(period_txns),
    )
    db.add(stmt)
    db.commit()
    db.refresh(stmt)
    return stmt


def list_statements(db: Session, user: User, account_id: str) -> list[Statement]:
    _enforce_account_ownership(db, user, account_id)
    return db.query(Statement).filter(Statement.account_id == account_id).all()


def get_statement(db: Session, user: User, statement_id: str) -> Statement:
    stmt = db.query(Statement).filter(Statement.id == statement_id).first()
    if not stmt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Statement not found")
    _enforce_account_ownership(db, user, stmt.account_id)
    return stmt
