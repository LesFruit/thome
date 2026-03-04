"""Transfer business logic — atomic double-entry with idempotency."""

from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.account import Account, AccountHolder
from app.models.transaction import Transaction, Transfer
from app.models.user import User


def _enforce_account_ownership(db: Session, user: User, account_id: str) -> Account:
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    holder = db.query(AccountHolder).filter(AccountHolder.id == account.holder_id).first()
    if not holder or holder.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return account


def create_transfer(
    db: Session,
    user: User,
    source_account_id: str,
    destination_account_id: str,
    amount_cents: int,
    idempotency_key: str,
) -> tuple[Transfer, bool]:
    """Returns (transfer, is_new). is_new=False means idempotency replay."""

    # Idempotency check
    existing = db.query(Transfer).filter(Transfer.idempotency_key == idempotency_key).first()
    if existing:
        return existing, False

    # Validate
    if source_account_id == destination_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot transfer to same account",
        )

    if amount_cents <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amount must be positive",
        )

    src = _enforce_account_ownership(db, user, source_account_id)
    dst_account = db.query(Account).filter(Account.id == destination_account_id).first()
    if not dst_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Destination account not found",
        )

    if src.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source account is not active",
        )
    if dst_account.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Destination account is not active",
        )

    # Atomic guarded debit — prevents overdraft without check-then-act race
    result = db.execute(
        update(Account)
        .where(Account.id == source_account_id)
        .where(Account.balance_cents >= amount_cents)
        .values(balance_cents=Account.balance_cents - amount_cents)
    )
    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient funds",
        )

    # Credit destination
    db.execute(
        update(Account)
        .where(Account.id == destination_account_id)
        .values(balance_cents=Account.balance_cents + amount_cents)
    )

    # Create transfer record
    transfer = Transfer(
        source_account_id=source_account_id,
        destination_account_id=destination_account_id,
        amount_cents=amount_cents,
        idempotency_key=idempotency_key,
        user_id=user.id,
    )
    db.add(transfer)
    db.flush()  # get transfer.id

    # Double-entry ledger: debit + credit transaction records
    db.add(
        Transaction(
            account_id=source_account_id,
            transfer_id=transfer.id,
            type="debit",
            amount_cents=amount_cents,
            description=f"Transfer to {destination_account_id}",
        )
    )
    db.add(
        Transaction(
            account_id=destination_account_id,
            transfer_id=transfer.id,
            type="credit",
            amount_cents=amount_cents,
            description=f"Transfer from {source_account_id}",
        )
    )

    db.commit()
    db.refresh(transfer)
    return transfer, True


def list_transfers(db: Session, user: User) -> list[Transfer]:
    return db.query(Transfer).filter(Transfer.user_id == user.id).all()


def get_transfer(db: Session, user: User, transfer_id: str) -> Transfer:
    transfer = db.query(Transfer).filter(Transfer.id == transfer_id).first()
    if not transfer or transfer.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer not found")
    return transfer


def deposit(db: Session, user: User, account_id: str, amount_cents: int) -> Account:
    """Internal deposit for seeding/testing. Creates a credit transaction."""
    account = _enforce_account_ownership(db, user, account_id)
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
    account.balance_cents += amount_cents
    db.add(
        Transaction(
            account_id=account_id,
            type="deposit",
            amount_cents=amount_cents,
            description="Deposit",
        )
    )
    db.commit()
    db.refresh(account)
    return account


def list_transactions(db: Session, user: User, account_id: str) -> list[Transaction]:
    _enforce_account_ownership(db, user, account_id)
    return (
        db.query(Transaction)
        .filter(Transaction.account_id == account_id)
        .order_by(Transaction.created_at)
        .all()
    )
