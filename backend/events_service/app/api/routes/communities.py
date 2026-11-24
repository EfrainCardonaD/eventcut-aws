from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from events_service.app.core.exceptions import AppError
from events_service.app.core.settings import settings
from events_service.app.db.session import get_db
from events_service.app.gateway.auth_client import auth_gateway_client
from events_service.app.models import Community, CommunityEventStatus
from events_service.app.schemas.auth import CurrentUser
from events_service.app.schemas.common import ApiResponse
from events_service.app.schemas.community import (
    CommunityCreate,
    CommunityEventRequestAction,
    CommunityEventRequestListItem,
    CommunityEventRequestListResponse,
    CommunityEventRequestResponse,
    CommunityListResponse,
    CommunityPublicListResponse,
    CommunityPublicResponse,
    CommunityResponse,
    CommunityScheduleResponse,
    CommunityUpdate,
)
from events_service.app.security.ban_check import get_verified_user
from events_service.app.security.rate_limit import limit_public_communities_reads
from events_service.app.services.community_service import (
    create_community,
    delete_community,
    get_active_community_or_404,
    get_community_or_404,
    get_community_schedule,
    list_communities,
    list_community_requests,
    list_user_communities,
    request_event_to_community,
    review_community_request,
    update_community,
)
from events_service.app.services.community_subscription_service import (
    list_subscribed_communities,
    subscribe_to_community,
    unsubscribe_from_community,
)
from events_service.app.services.event_service import get_event_or_404
from events_service.app.services.storage_service import generate_presigned_upload_url

router = APIRouter(prefix="/v1/communities", tags=["communities"])

AllowedImageContentType = Literal[
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/avif",
]


def _safe_fetch_owner_name(owner_id: str) -> tuple[str | None, str | None]:
    try:
        owner_name = auth_gateway_client.fetch_user_name(owner_id)
    except AppError:
        return None, None

    if owner_name is None:
        return None, None
    return owner_name


def _build_owner_name_index(owner_ids: set[str]) -> dict[str, tuple[str | None, str | None]]:
    if not owner_ids:
        return {}

    try:
        batch_index = auth_gateway_client.fetch_users_name_map(owner_ids)
        return {owner_id: batch_index.get(owner_id, (None, None)) for owner_id in owner_ids}
    except AppError:
        return {owner_id: _safe_fetch_owner_name(owner_id) for owner_id in owner_ids}


def _build_community_response(
    community,
    events_count: int = 0,
    owner_name_index: dict[str, tuple[str | None, str | None]] | None = None,
) -> CommunityResponse:
    if owner_name_index is None:
        owner_first_name, owner_last_name = _safe_fetch_owner_name(community.owner_id)
    else:
        owner_first_name, owner_last_name = owner_name_index.get(community.owner_id, (None, None))

    return CommunityResponse(
        id=community.id,
        name=community.name,
        description=community.description,
        image_url=community.image_url,
        owner_id=community.owner_id,
        owner_first_name=owner_first_name,
        owner_last_name=owner_last_name,
        contact_email=community.contact_email,
        category_id=getattr(community, "category_id", None),
        status=community.status,
        social_links=community.social_links,
        events_count=events_count,
        created_at=community.created_at,
    )


def _build_public_community_response(
    community,
    events_count: int = 0,
    owner_name_index: dict[str, tuple[str | None, str | None]] | None = None,
) -> CommunityPublicResponse:
    if owner_name_index is None:
        owner_first_name, owner_last_name = _safe_fetch_owner_name(community.owner_id)
    else:
        owner_first_name, owner_last_name = owner_name_index.get(community.owner_id, (None, None))

    return CommunityPublicResponse(
        id=community.id,
        name=community.name,
        description=community.description,
        image_url=community.image_url,
        owner_id=community.owner_id,
        owner_first_name=owner_first_name,
        owner_last_name=owner_last_name,
        contact_email=community.contact_email,
        category_id=getattr(community, "category_id", None),
        status=community.status,
        social_links=community.social_links,
        events_count=events_count,
        created_at=community.created_at,
    )


@router.post("", response_model=ApiResponse[CommunityResponse], status_code=status.HTTP_201_CREATED)
def post_community(
    payload: CommunityCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_verified_user),
) -> ApiResponse[CommunityResponse]:
    """Solicita crear una nueva comunidad. Entra en estado PENDING."""
    community = create_community(db, payload, current_user)
    data = _build_community_response(community)
    return ApiResponse(
        success=True,
        message="Solicitud de comunidad enviada. Pendiente de aprobación.",
        data=data,
    )


@router.get("", response_model=ApiResponse[CommunityPublicListResponse])
def get_communities(
    search: str | None = Query(default=None, max_length=120),
    category_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=settings.max_pagination_offset),
    db: Session = Depends(get_db),
    _: None = Depends(limit_public_communities_reads),
) -> ApiResponse[CommunityPublicListResponse]:
    """Lista comunidades activas. Público."""
    rows, total = list_communities(db, search=search, category_id=category_id, limit=limit, offset=offset)

    # Build owner name index for efficiency
    owner_ids = {community.owner_id for community, _ in rows}
    owner_name_index = _build_owner_name_index(owner_ids)

    items = []
    for community, events_count in rows:
        items.append(
            _build_public_community_response(
                community,
                events_count=events_count,
                owner_name_index=owner_name_index,
            )
        )

    return ApiResponse(
        success=True,
        message="Comunidades obtenidas",
        data=CommunityPublicListResponse(items=items, total=total),
    )


@router.get("/my", response_model=ApiResponse[CommunityListResponse])
def get_my_communities(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=settings.max_pagination_offset),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_verified_user),
) -> ApiResponse[CommunityListResponse]:
    """Lista las comunidades del usuario autenticado."""
    items, total = list_user_communities(db, current_user.id, limit=limit, offset=offset)

    owner_name_index = _build_owner_name_index({community.owner_id for community in items})

    return ApiResponse(
        success=True,
        message="Mis comunidades obtenidas",
        data=CommunityListResponse(
            items=[_build_community_response(c, owner_name_index=owner_name_index) for c in items],
            total=total,
        ),
    )


@router.get("/{community_id}", response_model=ApiResponse[CommunityPublicResponse])
def get_community(
    community_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(limit_public_communities_reads),
) -> ApiResponse[CommunityPublicResponse]:
    """Obtiene detalle de una comunidad. Público."""
    community = get_community_or_404(db, community_id)
    owner_name_index = _build_owner_name_index({community.owner_id})
    data = _build_public_community_response(community, owner_name_index=owner_name_index)
    return ApiResponse(success=True, message="Comunidad obtenida", data=data)


@router.patch("/{community_id}", response_model=ApiResponse[CommunityResponse])
def patch_community(
    community_id: str,
    payload: CommunityUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_verified_user),
) -> ApiResponse[CommunityResponse]:
    """Actualiza una comunidad. Solo el owner."""
    community = get_community_or_404(db, community_id)
    updated = update_community(db, community, payload, current_user)
    data = _build_community_response(updated)
    return ApiResponse(success=True, message="Comunidad actualizada", data=data)


@router.post("/image-upload-url", status_code=status.HTTP_200_OK)
def get_community_image_upload_url(
    content_type: AllowedImageContentType = Query(...),
    current_user: CurrentUser = Depends(get_verified_user),
) -> ApiResponse[dict]:
    """Devuelve URL pre-firmada para cargar imagenes temporales de comunidades."""
    data = generate_presigned_upload_url(content_type=content_type, namespace="comunidad")
    return ApiResponse(success=True, message="URL de carga generada", data=data)


@router.delete("/{community_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_community(
    community_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_verified_user),
) -> None:
    """Elimina una comunidad (soft delete). Solo el owner."""
    community = get_community_or_404(db, community_id)
    delete_community(db, community, current_user)


# ============== Community Subscriptions ==============


@router.post("/{community_id}/subscribe", response_model=ApiResponse[dict], status_code=status.HTTP_200_OK)
def post_subscribe_to_community(
    community_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_verified_user),
) -> ApiResponse[dict]:
    """Suscribe al usuario autenticado a una comunidad (idempotente)."""
    subscribe_to_community(db, community_id, current_user)
    return ApiResponse(success=True, message="Suscripción registrada", data={"community_id": community_id})


@router.delete("/{community_id}/subscribe", status_code=status.HTTP_204_NO_CONTENT)
def delete_subscribe_to_community(
    community_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_verified_user),
) -> None:
    """Elimina la suscripción del usuario autenticado a una comunidad (idempotente)."""
    unsubscribe_from_community(db, community_id, current_user)


@router.get("/my/subscriptions", response_model=ApiResponse[CommunityListResponse])
def get_my_subscribed_communities(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=settings.max_pagination_offset),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_verified_user),
) -> ApiResponse[CommunityListResponse]:
    """Lista las comunidades a las que el usuario autenticado está suscrito."""
    community_ids, total = list_subscribed_communities(db, current_user, limit=limit, offset=offset)

    if not community_ids:
        return ApiResponse(
            success=True,
            message="Mis suscripciones obtenidas",
            data=CommunityListResponse(items=[], total=0),
        )

    # Respeta el orden devuelto por la tabla de suscripciones.
    communities = {
        c.id: c
        for c in db.query(Community).filter(
            Community.id.in_(community_ids),
            Community.is_active == True,  # noqa: E712
        )
    }

    owner_name_index = _build_owner_name_index({c.owner_id for c in communities.values()})
    items = [
        _build_community_response(communities[cid], owner_name_index=owner_name_index)
        for cid in community_ids
        if cid in communities
    ]

    return ApiResponse(
        success=True,
        message="Mis suscripciones obtenidas",
        data=CommunityListResponse(items=items, total=total),
    )


# ============== Community Events Schedule ==============


@router.get("/{community_id}/events", response_model=ApiResponse[CommunityScheduleResponse])
def get_community_events(
    community_id: str,
    from_datetime: datetime | None = Query(default=None, alias="from"),
    to_datetime: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=settings.max_pagination_offset),
    db: Session = Depends(get_db),
    _: None = Depends(limit_public_communities_reads),
) -> ApiResponse[CommunityScheduleResponse]:
    """Obtiene el schedule de eventos de una comunidad. Público."""
    community = get_active_community_or_404(db, community_id)
    events, total = get_community_schedule(
        db, community, from_datetime=from_datetime, to_datetime=to_datetime, limit=limit, offset=offset
    )

    return ApiResponse(
        success=True,
        message="Eventos de la comunidad obtenidos",
        data=CommunityScheduleResponse(
            community={"id": community.id, "name": community.name},
            items=[
                {
                    "id": e.id,
                    "title": e.title,
                    "start_datetime": e.start_datetime,
                    "end_datetime": e.end_datetime,
                    "location": e.location,
                    "image_url": e.image_url,
                }
                for e in events
            ],
            total=total,
        ),
    )


# ============== Event Requests ==============


@router.post(
    "/{community_id}/events/{event_id}/request",
    response_model=ApiResponse[CommunityEventRequestResponse],
    status_code=status.HTTP_201_CREATED,
)
def post_event_request(
    community_id: str,
    event_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_verified_user),
) -> ApiResponse[CommunityEventRequestResponse]:
    """Solicita agregar un evento a una comunidad. Solo el dueño del evento."""
    community = get_active_community_or_404(db, community_id)
    event = get_event_or_404(db, event_id)

    request = request_event_to_community(db, community, event, current_user)

    return ApiResponse(
        success=True,
        message="Solicitud enviada al dueño de la comunidad",
        data=CommunityEventRequestResponse(
            request_id=request.id,
            community_id=request.community_id,
            event_id=request.event_id,
            status=request.status,
            requested_by=request.requested_by,
            created_at=request.created_at,
        ),
    )


@router.get("/{community_id}/requests", response_model=ApiResponse[CommunityEventRequestListResponse])
def get_community_requests(
    community_id: str,
    status_filter: CommunityEventStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=settings.max_pagination_offset),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_verified_user),
) -> ApiResponse[CommunityEventRequestListResponse]:
    """Lista solicitudes para una comunidad.

    - Owner de comunidad: ve todas.
    - Owner de evento: ve solo solicitudes de sus eventos.
    """
    community = get_community_or_404(db, community_id)
    requests, total = list_community_requests(
        db, community, current_user, status_filter=status_filter, limit=limit, offset=offset
    )

    owner_name_index = _build_owner_name_index({req.event.owner_id for req in requests})

    items = []
    for req in requests:
        event = req.event
        owner_first_name, owner_last_name = owner_name_index.get(event.owner_id, (None, None))
        items.append(
            CommunityEventRequestListItem(
                request_id=req.id,
                event={
                    "id": event.id,
                    "title": event.title,
                    "start_datetime": event.start_datetime,
                    "owner_id": event.owner_id,
                    "owner_first_name": owner_first_name,
                    "owner_last_name": owner_last_name,
                },
                status=req.status,
                requested_by=req.requested_by,
                reviewed_by=req.reviewed_by,
                reviewed_at=req.reviewed_at,
                rejection_reason=req.rejection_reason,
                created_at=req.created_at,
            )
        )

    return ApiResponse(
        success=True,
        message="Solicitudes obtenidas",
        data=CommunityEventRequestListResponse(items=items, total=total),
    )


@router.patch(
    "/{community_id}/requests/{request_id}",
    response_model=ApiResponse[CommunityEventRequestResponse],
)
def patch_request_status(
    community_id: str,
    request_id: str,
    payload: CommunityEventRequestAction,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_verified_user),
) -> ApiResponse[CommunityEventRequestResponse]:
    """Aprueba o rechaza una solicitud de evento. Solo el owner de la comunidad."""
    community = get_community_or_404(db, community_id)

    request = review_community_request(
        db,
        community,
        request_id,
        payload.action,
        current_user,
        payload.rejection_reason,
    )

    message = "Solicitud aprobada exitosamente" if payload.action == "APPROVE" else "Solicitud rechazada"

    return ApiResponse(
        success=True,
        message=message,
        data=CommunityEventRequestResponse(
            request_id=request.id,
            community_id=request.community_id,
            event_id=request.event_id,
            status=request.status,
            requested_by=request.requested_by,
            reviewed_by=request.reviewed_by,
            reviewed_at=request.reviewed_at,
            rejection_reason=request.rejection_reason,
            created_at=request.created_at,
        ),
    )
