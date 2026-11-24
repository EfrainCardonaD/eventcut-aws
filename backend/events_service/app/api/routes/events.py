from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from events_service.app.core.exceptions import AppError
from events_service.app.core.settings import settings
from events_service.app.db.session import get_db
from events_service.app.gateway.auth_client import auth_gateway_client
from events_service.app.schemas.auth import CurrentUser
from events_service.app.schemas.common import ApiResponse
from events_service.app.schemas.event import (
    EventCreate,
    EventFilters,
    EventListResponse,
    EventResponse,
    EventUpdate,
    FavoriteToggleResponse,
)
from events_service.app.security.ban_check import get_verified_user
from events_service.app.security.rate_limit import limit_public_events_reads
from events_service.app.services.event_service import (
    create_event,
    delete_event,
    get_event_or_404,
    get_event_with_score_or_404,
    list_events,
    list_user_favorite_events,
    toggle_favorite,
    update_event,
)
from events_service.app.services.storage_service import generate_presigned_upload_url

router = APIRouter(prefix="/v1/events", tags=["events"])

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


def _build_event_response(
    *,
    event,
    score: int,
    owner_name_index: dict[str, tuple[str | None, str | None]] | None = None,
) -> EventResponse:
    if owner_name_index is None:
        owner_first_name, owner_last_name = _safe_fetch_owner_name(event.owner_id)
    else:
        owner_first_name, owner_last_name = owner_name_index.get(event.owner_id, (None, None))

    return EventResponse.model_validate(
        {
            **event.__dict__,
            "score": int(score),
            "owner_first_name": owner_first_name,
            "owner_last_name": owner_last_name,
        }
    )


@router.get("", response_model=ApiResponse[EventListResponse])
def get_events(
    category_id: int | None = None,
    from_datetime: datetime | None = Query(default=None, alias="from"),
    to_datetime: datetime | None = Query(default=None, alias="to"),
    month: str | None = None,
    week_start: date | None = None,
    sort_by: Literal["start_datetime", "score"] = "start_datetime",
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=settings.max_pagination_offset),
    db: Session = Depends(get_db),
    _: None = Depends(limit_public_events_reads),
) -> ApiResponse[EventListResponse]:
    filters = EventFilters(
        category_id=category_id,
        **{"from": from_datetime},
        **{"to": to_datetime},
        month=month,
        week_start=week_start,
        sort_by=sort_by,
        limit=limit,
        offset=offset,
    )

    rows, total = list_events(db, filters)
    owner_name_index = _build_owner_name_index({event.owner_id for event, _ in rows})
    items = [_build_event_response(event=event, score=int(score), owner_name_index=owner_name_index) for event, score in rows]
    return ApiResponse(
        success=True,
        message="Eventos obtenidos",
        data=EventListResponse(items=items, total=total),
    )


@router.get("/my/favorites", response_model=ApiResponse[EventListResponse])
def get_my_favorite_events(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=settings.max_pagination_offset),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_verified_user),
) -> ApiResponse[EventListResponse]:
    rows, total = list_user_favorite_events(db, current_user.id, limit=limit, offset=offset)
    owner_name_index = _build_owner_name_index({event.owner_id for event, _ in rows})
    items = [_build_event_response(event=event, score=int(score), owner_name_index=owner_name_index) for event, score in rows]
    return ApiResponse(
        success=True,
        message="Mis favoritos obtenidos",
        data=EventListResponse(items=items, total=total),
    )


@router.get("/{event_id}", response_model=ApiResponse[EventResponse])
def get_event(
    event_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(limit_public_events_reads),
) -> ApiResponse[EventResponse]:
    event, score = get_event_with_score_or_404(db, event_id)
    data = _build_event_response(event=event, score=int(score))
    return ApiResponse(success=True, message="Evento obtenido", data=data)


@router.post("", response_model=ApiResponse[EventResponse], status_code=status.HTTP_201_CREATED)
def post_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_verified_user),
) -> ApiResponse[EventResponse]:
    event = create_event(db, payload, current_user)
    data = _build_event_response(event=event, score=0)
    return ApiResponse(success=True, message="Evento creado", data=data)


@router.patch("/{event_id}", response_model=ApiResponse[EventResponse])
def patch_event(
    event_id: str,
    payload: EventUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_verified_user),
) -> ApiResponse[EventResponse]:
    event = get_event_or_404(db, event_id)
    updated = update_event(db, event, payload, current_user)
    data = _build_event_response(event=updated, score=0)
    return ApiResponse(success=True, message="Evento actualizado", data=data)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_event(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_verified_user),
) -> None:
    event = get_event_or_404(db, event_id)
    delete_event(db, event, current_user)


@router.post("/{event_id}/favorite", response_model=ApiResponse[FavoriteToggleResponse])
def post_favorite_toggle(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_verified_user),
) -> ApiResponse[FavoriteToggleResponse]:
    favorited = toggle_favorite(db, event_id, current_user)
    data = FavoriteToggleResponse(event_id=event_id, favorited=favorited)
    message = "Marcado como favorito" if favorited else "Eliminado de favoritos"
    return ApiResponse(success=True, message=message, data=data)


@router.post("/image-upload-url", status_code=status.HTTP_200_OK)
def get_image_upload_url(
    content_type: AllowedImageContentType = Query(...),
    current_user: CurrentUser = Depends(get_verified_user),
) -> ApiResponse[dict]:
    """
    Devuelve una URL pre-firmada. El cliente debe hacer un PUT a esta URL con el binario de la imagen.
    """
    data = generate_presigned_upload_url(content_type=content_type, namespace="events")
    return ApiResponse(success=True, message="URL de carga generada", data=data)

