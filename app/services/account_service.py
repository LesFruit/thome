"""Business logic for account holders and accounts."""

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.account import ACCOUNT_STATUS_TRANSITIONS, Account, AccountHolder
from app.models.user import User

# --- Holders ---

def create_holder(
    db: Session, user: User, first_name: str, last_name: str, dob: date,
) -> AccountHolder:
    existing = db.query(AccountHolder).filter(
        AccountHolder.user_id == user.id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Holder already exists for this user",
        )

    holder = AccountHolder(
        user_id=user.id, first_name=first_name,
        last_name=last_name, date_of_birth=dob,
    )
    db.add(holder)
    db.commit()
    db.refresh(holder)
    return holder


def get_holder(db: Session, user: User) -> AccountHolder:
    holder = db.query(AccountHolder).filter(AccountHolder.user_id == user.id).first()
    if not holder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holder not found")
    return holder


def update_holder(db: Session, user: User, **fields) -> AccountHolder:
    holder = get_holder(db, user)
    for key, value in fields.items():
        if value is not None:
            setattr(holder, key, value)
    db.commit()
    db.refresh(holder)
    return holder


# --- Accounts ---

def _get_holder_for_user(db: Session, user: User) -> AccountHolder:
    holder = db.query(AccountHolder).filter(AccountHolder.user_id == user.id).first()
    if not holder:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Create an account holder first",
        )
    return holder


def create_account(db: Session, user: User, account_type: str) -> Account:
    holder = _get_holder_for_user(db, user)
    account = Account(holder_id=holder.id, account_type=account_type)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def list_accounts(db: Session, user: User) -> list[Account]:
    holder = _get_holder_for_user(db, user)
    return db.query(Account).filter(Account.holder_id == holder.id).all()


def get_account(db: Session, user: User, account_id: str) -> Account:
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    _enforce_ownership(db, user, account)
    return account


def update_account_status(db: Session, user: User, account_id: str, new_status: str) -> Account:
    account = get_account(db, user, account_id)
    allowed = ACCOUNT_STATUS_TRANSITIONS.get(account.status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition from '{account.status}' to '{new_status}'",
        )
    account.status = new_status
    db.commit()
    db.refresh(account)
    return account


def _enforce_ownership(db: Session, user: User, account: Account) -> None:
    holder = db.query(AccountHolder).filter(AccountHolder.id == account.holder_id).first()
    if not holder or holder.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
