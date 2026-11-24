from __future__ import annotations

from datetime import datetime

from fastapi import status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from events_service.app.core.exceptions import AppError, ErrorCodes
from events_service.app.models import (
    Category,
    Community,
    CommunityEvent,
    CommunityEventStatus,
    CommunityStatus,
    Event,
)
from events_service.app.schemas.auth import CurrentUser
from events_service.app.schemas.community import CommunityCreate, CommunityUpdate
from events_service.app.services.storage_service import (
    build_public_url,
    delete_object,
    extract_file_key_from_public_url,
    is_pending_key,
    promote_pending_object,
)


def create_community(db: Session, payload: CommunityCreate, current_user: CurrentUser) -> Community:
    """Crea una nueva solicitud de comunidad."""
    if not payload.is_accepted_terms:
        raise AppError(
            code=ErrorCodes.TERMS_NOT_ACCEPTED,
            message="Debes aceptar los términos y condiciones",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Verificar nombre único
    existing = db.query(Community).filter(
        Community.name == payload.name,
        Community.is_active == True,  # noqa: E712
    ).first()

    if existing:
        raise AppError(
            code=ErrorCodes.DUPLICATE_COMMUNITY_NAME,
            message="Ya existe una comunidad con ese nombre",
            status_code=status.HTTP_409_CONFLICT,
        )

    image_url = payload.image_url
    promoted_key: str | None = None
    incoming_key = extract_file_key_from_public_url(payload.image_url)
    if incoming_key and is_pending_key(incoming_key, namespace="comunidad"):
        promoted_key = promote_pending_object(incoming_key, namespace="comunidad")
        image_url = build_public_url(promoted_key)

    if payload.category_id is not None:
        category = db.get(Category, payload.category_id)
        if category is None:
            raise AppError(
                code=ErrorCodes.CATEGORY_INVALID,
                message="La categoría indicada no existe",
                status_code=status.HTTP_400_BAD_REQUEST,
                details={"category_id": payload.category_id},
            )

    community = Community(
        name=payload.name,
        description=payload.description,
        image_url=image_url,
        owner_id=current_user.id,
        contact_email=payload.contact_email,
        category_id=payload.category_id,
        is_accepted_terms=payload.is_accepted_terms,
        social_links=payload.social_links.to_dict() if payload.social_links else None,
        status=CommunityStatus.PENDING,
    )
    db.add(community)
    try:
        db.commit()
    except Exception:
        db.rollback()
        if promoted_key:
            try:
                delete_object(promoted_key)
            except AppError:
                pass
        raise
    db.refresh(community)
    return community


def get_community_or_404(db: Session, community_id: str) -> Community:
    """Obtiene una comunidad por ID o lanza 404."""
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
    return community


def get_active_community_or_404(db: Session, community_id: str) -> Community:
    """Obtiene una comunidad ACTIVA por ID o lanza error."""
    community = get_community_or_404(db, community_id)

    if community.status != CommunityStatus.ACTIVE:
        raise AppError(
            code=ErrorCodes.COMMUNITY_NOT_ACTIVE,
            message="La comunidad no está activa",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return community


def list_communities(
    db: Session,
    *,
    search: str | None = None,
    category_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[tuple[Community, int]], int]:
    """Lista comunidades activas con conteo de eventos."""
    # Subquery para contar eventos aprobados por comunidad
    events_count_subq = (
        db.query(
            CommunityEvent.community_id,
            func.count(CommunityEvent.id).label("events_count"),
        )
        .filter(CommunityEvent.status == CommunityEventStatus.APPROVED)
        .group_by(CommunityEvent.community_id)
        .subquery()
    )

    query = (
        db.query(Community, func.coalesce(events_count_subq.c.events_count, 0))
        .outerjoin(events_count_subq, Community.id == events_count_subq.c.community_id)
        .filter(
            Community.is_active == True,  # noqa: E712
            Community.status == CommunityStatus.ACTIVE,
        )
    )

    if search:
        query = query.filter(Community.name.ilike(f"%{search}%"))

    if category_id is not None:
        query = query.filter(Community.category_id == category_id)

    total = query.count()
    items = query.order_by(Community.created_at.desc()).offset(offset).limit(limit).all()

    return items, total


def update_community(
    db: Session,
    community: Community,
    payload: CommunityUpdate,
    current_user: CurrentUser,
) -> Community:
    """Actualiza una comunidad. Solo el owner puede hacerlo."""
    if community.owner_id != current_user.id:
        raise AppError(
            code=ErrorCodes.NOT_COMMUNITY_OWNER,
            message="No eres el dueño de esta comunidad",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    # Verificar nombre único si se está cambiando
    if payload.name and payload.name != community.name:
        existing = db.query(Community).filter(
            Community.name == payload.name,
            Community.is_active == True,  # noqa: E712
            Community.id != community.id,
        ).first()
        if existing:
            raise AppError(
                code=ErrorCodes.DUPLICATE_COMMUNITY_NAME,
                message="Ya existe una comunidad con ese nombre",
                status_code=status.HTTP_409_CONFLICT,
            )

    update_data = payload.model_dump(exclude_unset=True)

    # Prevenir que envíen null a un campo que es obligatorio en DB
    if "contact_email" in update_data and update_data["contact_email"] is None:
        del update_data["contact_email"]

    if "category_id" in update_data and update_data["category_id"] is not None:
        category = db.get(Category, update_data["category_id"])
        if category is None:
            raise AppError(
                code=ErrorCodes.CATEGORY_INVALID,
                message="La categoría indicada no existe",
                status_code=status.HTTP_400_BAD_REQUEST,
                details={"category_id": update_data["category_id"]},
            )

    if "social_links" in update_data and update_data["social_links"]:
        update_data["social_links"] = payload.social_links.to_dict()

    old_image_key = extract_file_key_from_public_url(community.image_url)
    promoted_new_key: str | None = None
    old_image_to_delete_after_commit: str | None = None

    if "image_url" in update_data:
        requested_image_url = update_data["image_url"]
        requested_key = extract_file_key_from_public_url(requested_image_url)

        if requested_key and is_pending_key(requested_key, namespace="comunidad"):
            promoted_new_key = promote_pending_object(requested_key, namespace="comunidad")
            update_data["image_url"] = build_public_url(promoted_new_key)
            if old_image_key and old_image_key != promoted_new_key:
                old_image_to_delete_after_commit = old_image_key
        elif requested_image_url is None:
            if old_image_key:
                old_image_to_delete_after_commit = old_image_key
        elif requested_key and old_image_key and requested_key != old_image_key:
            old_image_to_delete_after_commit = old_image_key

    for key, value in update_data.items():
        setattr(community, key, value)

    try:
        db.commit()
    except Exception:
        db.rollback()
        if promoted_new_key:
            try:
                delete_object(promoted_new_key)
            except AppError:
                pass
        raise

    if old_image_to_delete_after_commit:
        try:
            delete_object(old_image_to_delete_after_commit)
        except AppError:
            # Best effort: no bloqueamos la actualizacion por limpieza diferida.
            pass

    db.refresh(community)
    return community


def delete_community(db: Session, community: Community, current_user: CurrentUser) -> None:
    """Elimina una comunidad (soft delete). Solo el owner puede hacerlo."""
    if community.owner_id != current_user.id:
        raise AppError(
            code=ErrorCodes.NOT_COMMUNITY_OWNER,
            message="No eres el dueño de esta comunidad",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    community.is_active = False
    db.commit()


def request_event_to_community(
    db: Session,
    community: Community,
    event: Event,
    current_user: CurrentUser,
) -> CommunityEvent:
    """Solicita agregar un evento a una comunidad."""
    # Solo el dueño del evento puede solicitar
    if event.owner_id != current_user.id:
        raise AppError(
            code=ErrorCodes.NOT_EVENT_OWNER,
            message="No eres el dueño de este evento",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    # Verificar que no exista ya una solicitud
    existing = db.query(CommunityEvent).filter(
        CommunityEvent.community_id == community.id,
        CommunityEvent.event_id == event.id,
    ).first()

    if existing:
        raise AppError(
            code=ErrorCodes.EVENT_ALREADY_REQUESTED,
            message=f"Ya existe una solicitud con estado {existing.status}",
            status_code=status.HTTP_409_CONFLICT,
        )

    request = CommunityEvent(
        community_id=community.id,
        event_id=event.id,
        requested_by=current_user.id,
        status=CommunityEventStatus.PENDING,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def list_community_requests(
    db: Session,
    community: Community,
    current_user: CurrentUser,
    *,
    status_filter: CommunityEventStatus | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[CommunityEvent], int]:
    """Lista solicitudes de eventos para una comunidad.

    - Owner de comunidad: puede ver todas las solicitudes.
    - Owner de evento: puede ver solo solicitudes de sus eventos para esa comunidad.
    """
    is_community_owner = community.owner_id == current_user.id
    base_query = db.query(CommunityEvent).filter(CommunityEvent.community_id == community.id)

    if is_community_owner:
        query = base_query
    else:
        query = base_query.join(Event, Event.id == CommunityEvent.event_id).filter(Event.owner_id == current_user.id)

        if not db.query(CommunityEvent.id).join(Event, Event.id == CommunityEvent.event_id).filter(
            CommunityEvent.community_id == community.id,
            Event.owner_id == current_user.id,
        ).first():
            raise AppError(
                code=ErrorCodes.NOT_COMMUNITY_OWNER,
                message="No tienes permisos para ver solicitudes de esta comunidad",
                status_code=status.HTTP_403_FORBIDDEN,
            )

    if status_filter:
        query = query.filter(CommunityEvent.status == status_filter)

    total = query.count()
    items = (
        query.options(joinedload(CommunityEvent.event))
        .order_by(CommunityEvent.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return items, total


def review_community_request(
    db: Session,
    community: Community,
    request_id: str,
    action: str,
    current_user: CurrentUser,
    rejection_reason: str | None = None,
) -> CommunityEvent:
    """Aprueba o rechaza una solicitud de evento. Solo el owner de la comunidad."""
    if community.owner_id != current_user.id:
        raise AppError(
            code=ErrorCodes.NOT_COMMUNITY_OWNER,
            message="No eres el dueño de esta comunidad",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    request = db.query(CommunityEvent).filter(
        CommunityEvent.id == request_id,
        CommunityEvent.community_id == community.id,
    ).first()

    if not request:
        raise AppError(
            code=ErrorCodes.REQUEST_NOT_FOUND,
            message="Solicitud no encontrada",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if request.status != CommunityEventStatus.PENDING:
        raise AppError(
            code=ErrorCodes.VALIDATION_ERROR,
            message=f"La solicitud ya tiene estado {request.status}",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if action == "APPROVE":
        request.status = CommunityEventStatus.APPROVED
    else:
        if not rejection_reason:
            raise AppError(
                code=ErrorCodes.VALIDATION_ERROR,
                message="Se requiere razón de rechazo",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        request.status = CommunityEventStatus.REJECTED
        request.rejection_reason = rejection_reason

    request.reviewed_by = current_user.id
    request.reviewed_at = datetime.now()

    db.commit()
    db.refresh(request)
    return request


def get_community_schedule(
    db: Session,
    community: Community,
    *,
    from_datetime: datetime | None = None,
    to_datetime: datetime | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Event], int]:
    """Obtiene los eventos aprobados de una comunidad."""
    query = (
        db.query(Event)
        .join(CommunityEvent, CommunityEvent.event_id == Event.id)
        .filter(
            CommunityEvent.community_id == community.id,
            CommunityEvent.status == CommunityEventStatus.APPROVED,
            Event.is_active == True,  # noqa: E712
        )
    )

    if from_datetime:
        query = query.filter(Event.start_datetime >= from_datetime)
    if to_datetime:
        query = query.filter(Event.start_datetime <= to_datetime)

    total = query.count()
    items = query.order_by(Event.start_datetime.asc()).offset(offset).limit(limit).all()

    return items, total


def list_user_communities(
    db: Session,
    user_id: str,
    *,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Community], int]:
    """Lista las comunidades de un usuario."""
    query = db.query(Community).filter(
        Community.owner_id == user_id,
        Community.is_active == True,  # noqa: E712
    )

    total = query.count()
    items = query.order_by(Community.created_at.desc()).offset(offset).limit(limit).all()

    return items, total
