"""Account holder router."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.account import HolderCreateRequest, HolderResponse, HolderUpdateRequest
from app.services import account_service

router = APIRouter(prefix="/api/v1/holders", tags=["holders"])


@router.post("", response_model=HolderResponse, status_code=status.HTTP_201_CREATED)
def create_holder(
    req: HolderCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return account_service.create_holder(db, user, req.first_name, req.last_name, req.date_of_birth)


@router.get("/me", response_model=HolderResponse)
def get_holder(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return account_service.get_holder(db, user)


@router.patch("/me", response_model=HolderResponse)
def update_holder(
    req: HolderUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return account_service.update_holder(
        db, user,
        first_name=req.first_name,
        last_name=req.last_name,
        date_of_birth=req.date_of_birth,
    )
