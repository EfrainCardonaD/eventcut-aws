from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from auth.db.session import get_db
from auth.schemas.common import RestResponse
from auth.schemas.user import CurrentUser, UpdateUserRoleRequest, UpdateUserRoleResponse, UserResponse, UserSummaryResponse
from auth.security.dependencies import get_current_user, require_roles
from auth.services import auth_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=RestResponse[CurrentUser])
def me(current_user: CurrentUser = Depends(get_current_user)):
    return RestResponse(success=True, message="Perfil actual", data=current_user)


@router.get(
    "/{user_id}",
    response_model=RestResponse[UserResponse],
    dependencies=[Depends(require_roles("ROLE_ADMIN", "ROLE_SUPER_ADMIN", "ROLE_SECURITY_ADMIN"))],
)
def get_user_detail(user_id: str, db: Session = Depends(get_db)):
    user = auth_service.get_user_by_id(db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return RestResponse(success=True, message="Usuario encontrado", data=UserResponse.from_user(user))


@router.get(
    "",
    response_model=RestResponse[list[UserResponse]],
    dependencies=[Depends(require_roles("ROLE_ADMIN", "ROLE_SECURITY_ADMIN"))],
)
def list_users(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    users = auth_service.list_users(db, limit=limit, offset=offset)
    return RestResponse(success=True, message="Usuarios listados", data=[UserResponse.from_user(u) for u in users])


@router.patch(
    "/{user_id}/role",
    response_model=RestResponse[UpdateUserRoleResponse],
    dependencies=[Depends(require_roles("ROLE_ADMIN"))],
)
def update_role(user_id: str, req: UpdateUserRoleRequest, db: Session = Depends(get_db)):
    user = auth_service.update_user_role(db, user_id=user_id, role=req.role)
    response_data = UpdateUserRoleResponse.model_validate(
        {
            "id": user.id,
            "role": user.role,
            "token_version": user.token_version,
        }
    )
    return RestResponse(
        success=True,
        message="Rol actualizado",
        data=response_data,
    )


@router.get(
    "/internal/summary",
    response_model=RestResponse[dict[str, UserSummaryResponse]],
    dependencies=[Depends(require_roles("ROLE_ADMIN", "ROLE_SECURITY_ADMIN"))],
)
def get_users_summary(
    ids: list[str] = Query(default_factory=list, min_length=1, max_length=64, max_items=100),
    db: Session = Depends(get_db),
):
    if len(ids) > 100:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Máximo 100 ids por solicitud")
    users_by_id = auth_service.list_user_summaries_by_ids(db, user_ids=ids[:100])
    payload = {user_id: UserSummaryResponse.from_user(user) for user_id, user in users_by_id.items()}
    return RestResponse(success=True, message="Resumen de usuarios", data=payload)
