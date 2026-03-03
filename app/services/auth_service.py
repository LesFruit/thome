"""Auth business logic — signup, login, refresh, logout."""

import hashlib

import bcrypt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth.jwt import create_access_token, create_refresh_token, get_refresh_token_expiry
from app.models.user import RefreshToken, User


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _hash_refresh_token(raw_token: str) -> str:
    """Hash refresh token for DB storage (SHA-256, not bcrypt — lookup speed matters)."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def signup(db: Session, email: str, password: str) -> User:
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=email, hashed_password=_hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login(db: Session, email: str, password: str) -> dict:
    user = db.query(User).filter(User.email == email).first()
    if not user or not _verify_password(password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = create_access_token(user.id)
    raw_refresh = create_refresh_token(user.id)

    rt = RefreshToken(
        token_hash=_hash_refresh_token(raw_refresh),
        user_id=user.id,
        expires_at=get_refresh_token_expiry(),
    )
    db.add(rt)
    db.commit()

    return {"access_token": access_token, "refresh_token": raw_refresh, "token_type": "bearer"}


def refresh(db: Session, raw_refresh_token: str) -> dict:
    token_hash = _hash_refresh_token(raw_refresh_token)
    stored = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
        RefreshToken.revoked.is_(False),
    ).first()

    if not stored:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    user = db.query(User).filter(User.id == stored.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Revoke old token (rotation)
    stored.revoked = True

    # Issue new pair
    access_token = create_access_token(user.id)
    new_raw_refresh = create_refresh_token(user.id)

    new_rt = RefreshToken(
        token_hash=_hash_refresh_token(new_raw_refresh),
        user_id=user.id,
        expires_at=get_refresh_token_expiry(),
    )
    db.add(new_rt)
    db.commit()

    return {"access_token": access_token, "refresh_token": new_raw_refresh, "token_type": "bearer"}


def logout(db: Session, raw_refresh_token: str) -> None:
    token_hash = _hash_refresh_token(raw_refresh_token)
    stored = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if stored:
        stored.revoked = True
        db.commit()
