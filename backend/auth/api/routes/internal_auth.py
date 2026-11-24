from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth.db.session import get_db
from auth.models.user import User
from auth.schemas.user import CurrentUser
from auth.security.dependencies import get_current_user
from auth.security.gateway import require_gateway_secret


class InternalAuthUserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    active: bool
    email_verified: bool


router = APIRouter(prefix="/internal/auth", tags=["internal"], dependencies=[Depends(require_gateway_secret)])


@router.get("/me", response_model=InternalAuthUserResponse)
def internal_me(current_user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.get(User, current_user.id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    if not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inactivo")

    return InternalAuthUserResponse(
        id=str(user.id),
        username=str(user.username),
        email=str(user.email),
        role=str(user.role),
        active=bool(user.active),
        email_verified=bool(user.email_verified),
    )
