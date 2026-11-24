from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.db.session import get_db
from auth.models.user import User
from auth.schemas.user import UserResponse, UserSummaryResponse
from auth.security.gateway import require_gateway_secret
from auth.services import auth_service

router = APIRouter(prefix="/internal/users", tags=["internal"], dependencies=[Depends(require_gateway_secret)])


@router.get("/summary", response_model=dict[str, UserSummaryResponse])
def get_users_summary(
    ids: list[str] = Query(default_factory=list, min_length=1, max_length=64, max_items=100),
    db: Session = Depends(get_db),
):
    if len(ids) > 100:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Máximo 100 ids por solicitud")
    # Limite defensivo para evitar payloads excesivos en endpoint interno.
    bounded_ids = ids[:100]
    users_by_id = auth_service.list_user_summaries_by_ids(db, user_ids=bounded_ids)
    return {user_id: UserSummaryResponse.from_user(user) for user_id, user in users_by_id.items()}


@router.get("/{id}", response_model=UserResponse, responses={404: {"description": "Usuario no encontrado"}})
def get_user_by_id(id: str, db: Session = Depends(get_db)):
    user = db.get(User, id)
    if not user:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    return UserResponse.from_user(user)


@router.get(
    "/by-username/{username}",
    response_model=UserResponse,
    responses={404: {"description": "Usuario no encontrado"}},
)
def get_user_by_username(username: str, db: Session = Depends(get_db)):
    stmt = select(User).where(User.username == username)
    user = db.scalar(stmt)
    if not user:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    return UserResponse.from_user(user)


