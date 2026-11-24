from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from events_service.app.core.exceptions import AppError, ErrorCodes
from events_service.app.db.session import get_db
from events_service.app.models import Community, CommunityStatus
from events_service.app.schemas.admin import (
    AdminCommunityModerationItem,
    AdminCommunityModerationListResponse,
    BannedUserListResponse,
    BannedUserResponse,
    BanUserRequest,
    CommunityStatusAction,
    UnbanResponse,
)
from events_service.app.schemas.auth import CurrentUser
from events_service.app.schemas.common import ApiResponse
from events_service.app.security.admin_required import require_admin
from events_service.app.services.ban_service import (
    ban_user,
    get_ban_record,
    list_banned_users,
    unban_user,
)

router = APIRouter(prefix="/v1/admin", tags=["admin"])


# ============== User Ban Management ==============


@router.post("/users/{user_id}/ban", response_model=ApiResponse[dict])
def post_ban_user(
    user_id: UUID,
    payload: BanUserRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
) -> ApiResponse[BannedUserResponse]:
    """Banea a un usuario. Solo admins."""
    user_id_str = str(user_id)

    if user_id_str == current_user.id:
        raise AppError(
            code=ErrorCodes.VALIDATION_ERROR,
            message="No puedes banearte a ti mismo",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    ban, propagation = ban_user(db, user_id=user_id_str, reason=payload.reason, banned_by=current_user.id)
    data = BannedUserResponse(
        user_id=ban.user_id,
        reason=ban.reason,
        banned_by=ban.banned_by,
        banned_at=ban.banned_at,
        is_active=ban.is_active,
    )

    return ApiResponse(
        success=True,
        message="Usuario baneado exitosamente. Contenido despublicado.",
        data={
            "ban": data,
            "propagation": propagation,
        },
    )


@router.delete("/users/{user_id}/ban", response_model=ApiResponse[UnbanResponse])
def delete_ban_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
) -> ApiResponse[UnbanResponse]:
    """Desbanea a un usuario. Solo admins."""
    user_id_str = str(user_id)
    success = unban_user(db, user_id_str)
    if not success:
        raise AppError(
            code=ErrorCodes.VALIDATION_ERROR,
            message="El usuario no tiene baneo activo",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    data = UnbanResponse(user_id=user_id_str)
    return ApiResponse(success=True, message="Usuario desbaneado exitosamente", data=data)


@router.get("/users/banned", response_model=ApiResponse[BannedUserListResponse])
def get_banned_users(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
) -> ApiResponse[BannedUserListResponse]:
    """Lista usuarios baneados. Solo admins."""
    items, total = list_banned_users(db, limit=limit, offset=offset, include_inactive=include_inactive)
    data = BannedUserListResponse(
        items=[
            BannedUserResponse(
                user_id=b.user_id,
                reason=b.reason,
                banned_by=b.banned_by,
                banned_at=b.banned_at,
                is_active=b.is_active,
            )
            for b in items
        ],
        total=total,
    )
    return ApiResponse(success=True, message="Usuarios baneados obtenidos", data=data)


@router.get("/users/{user_id}/ban-status", response_model=ApiResponse)
def get_user_ban_status(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
) -> ApiResponse[BannedUserResponse | None]:
    """Verifica el estado de baneo de un usuario. Solo admins."""
    ban = get_ban_record(db, str(user_id))
    if not ban:
        return ApiResponse(success=True, message="El usuario no está baneado", data=None)

    data = BannedUserResponse(
        user_id=ban.user_id,
        reason=ban.reason,
        banned_by=ban.banned_by,
        banned_at=ban.banned_at,
        is_active=ban.is_active,
    )
    return ApiResponse(success=True, message="Usuario baneado", data=data)


# ============== Community Moderation ==============


@router.get("/communities", response_model=ApiResponse[AdminCommunityModerationListResponse])
def get_admin_communities(
    status_filter: CommunityStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
) -> ApiResponse[AdminCommunityModerationListResponse]:
    """Lista comunidades para moderación. Solo admins."""
    query = db.query(Community).filter(Community.is_active == True)  # noqa: E712

    if status_filter:
        query = query.filter(Community.status == status_filter)

    total = query.count()
    communities = query.order_by(Community.created_at.desc()).offset(offset).limit(limit).all()

    moderation_items: list[AdminCommunityModerationItem] = []
    for community in communities:
        moderation_items.append(
            AdminCommunityModerationItem(
                id=getattr(community, "id"),
                name=getattr(community, "name"),
                description=getattr(community, "description"),
                image_url=getattr(community, "image_url"),
                owner_id=getattr(community, "owner_id"),
                contact_email=getattr(community, "contact_email"),
                category_id=getattr(community, "category_id"),
                status=str(getattr(community, "status")),
                is_accepted_terms=getattr(community, "is_accepted_terms"),
                rejection_reason=getattr(community, "rejection_reason"),
                social_links=getattr(community, "social_links"),
                is_active=getattr(community, "is_active"),
                deactivated_at=getattr(community, "deactivated_at"),
                deactivated_by=getattr(community, "deactivated_by"),
                deactivated_reason=getattr(community, "deactivated_reason"),
                created_at=getattr(community, "created_at"),
                updated_at=getattr(community, "updated_at"),
            )
        )

    data = AdminCommunityModerationListResponse(items=moderation_items, total=total)

    return ApiResponse(
        success=True,
        message="Comunidades obtenidas",
        data=data,
    )


@router.patch("/communities/{community_id}/status")
def patch_community_status(
    community_id: str,
    payload: CommunityStatusAction,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
) -> ApiResponse:
    """Activa o rechaza una comunidad. Solo admins."""
    community = db.query(Community).filter(
        Community.id == community_id,
        Community.is_active == True,  # noqa: E712
    ).first()

    if not community:
        raise AppError(
            code=ErrorCodes.COMMUNITY_NOT_FOUND,
            message="Comunidad no encontrada",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if community.status != CommunityStatus.PENDING:
        raise AppError(
            code=ErrorCodes.VALIDATION_ERROR,
            message=f"La comunidad ya tiene estado {community.status}",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if payload.action == "ACTIVATE":
        community.status = CommunityStatus.ACTIVE
        message = "Comunidad activada exitosamente"
    else:  # REJECT
        if not payload.rejection_reason:
            raise AppError(
                code=ErrorCodes.VALIDATION_ERROR,
                message="Se requiere razón de rechazo",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        community.status = CommunityStatus.REJECTED
        community.rejection_reason = payload.rejection_reason
        message = "Comunidad rechazada"

    db.commit()
    db.refresh(community)

    return ApiResponse(
        success=True,
        message=message,
        data={"id": community.id, "status": community.status},
    )
