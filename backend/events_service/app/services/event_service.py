from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from fastapi import status
from sqlalchemy import Select, delete, func, select
from sqlalchemy.orm import Session

from events_service.app.core.exceptions import AppError, ErrorCodes
from events_service.app.models.category import Category
from events_service.app.models.community import Community, CommunityStatus
from events_service.app.models.community_event import CommunityEvent, CommunityEventStatus
from events_service.app.models.event import Event
from events_service.app.models.event_favorite import EventFavorite
from events_service.app.schemas.auth import CurrentUser
from events_service.app.schemas.event import EventCreate, EventFilters, EventUpdate
from events_service.app.security.roles import is_admin_role
from events_service.app.services.storage_service import (
    build_public_url,
    delete_object,
    extract_file_key_from_public_url,
    is_pending_key,
    promote_pending_object,
)


def _coerce_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _month_bounds(month: str) -> tuple[datetime, datetime]:
    try:
        year, month_num = month.split("-", maxsplit=1)
        first_day = date(int(year), int(month_num), 1)
    except ValueError as exc:
        raise AppError(
            code=ErrorCodes.MONTH_INVALID,
            message="El parámetro 'month' es inválido. Usa el formato YYYY-MM.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"month": month},
        ) from exc

    if first_day.month == 12:
        next_month = date(first_day.year + 1, 1, 1)
    else:
        next_month = date(first_day.year, first_day.month + 1, 1)

    return (
        datetime.combine(first_day, datetime.min.time(), tzinfo=UTC),
        datetime.combine(next_month, datetime.min.time(), tzinfo=UTC),
    )


def _week_bounds(week_start: date) -> tuple[datetime, datetime]:
    start = datetime.combine(week_start, datetime.min.time(), tzinfo=UTC)
    return start, start + timedelta(days=7)


def _effective_window(filters: EventFilters) -> tuple[datetime | None, datetime | None]:
    if filters.from_datetime and filters.to_datetime:
        return _coerce_utc(filters.from_datetime), _coerce_utc(filters.to_datetime)
    if filters.month:
        return _month_bounds(filters.month)
    if filters.week_start:
        return _week_bounds(filters.week_start)
    return None, None


def _score_subquery():
    return (
        select(
            EventFavorite.event_id.label("event_id"),
            func.count(EventFavorite.user_id).label("score"),
        )
        .group_by(EventFavorite.event_id)
        .subquery()
    )


def list_categories(db: Session) -> list[Category]:
    stmt = select(Category).order_by(Category.name.asc())
    return list(db.scalars(stmt).all())


def list_events(db: Session, filters: EventFilters) -> tuple[list[tuple[Event, int]], int]:
    score_sq = _score_subquery()

    stmt: Select = (
        select(Event, func.coalesce(score_sq.c.score, 0).label("score"))
        .outerjoin(score_sq, score_sq.c.event_id == Event.id)
        .where(Event.is_active.is_(True))
    )

    if filters.category_id:
        stmt = stmt.where(Event.category_id == filters.category_id)

    window_start, window_end = _effective_window(filters)
    if window_start:
        stmt = stmt.where(Event.start_datetime >= window_start)
    if window_end:
        stmt = stmt.where(Event.start_datetime < window_end)

    if filters.sort_by == "score":
        stmt = stmt.order_by(func.coalesce(score_sq.c.score, 0).desc(), Event.start_datetime.asc())
    else:
        stmt = stmt.order_by(Event.start_datetime.asc())

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = int(db.scalar(total_stmt) or 0)

    rows_raw = list(db.execute(stmt.offset(filters.offset).limit(filters.limit)).all())
    rows = [(row[0], int(row[1])) for row in rows_raw]
    return rows, total


def list_user_favorite_events(
    db: Session,
    user_id: str,
    *,
    limit: int,
    offset: int,
) -> tuple[list[tuple[Event, int]], int]:
    score_sq = _score_subquery()

    base_stmt: Select = (
        select(Event, func.coalesce(score_sq.c.score, 0).label("score"))
        .join(EventFavorite, EventFavorite.event_id == Event.id)
        .outerjoin(score_sq, score_sq.c.event_id == Event.id)
        .where(
            EventFavorite.user_id == user_id,
            Event.is_active.is_(True),
        )
        .order_by(EventFavorite.created_at.desc(), Event.start_datetime.asc())
    )

    total_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = int(db.scalar(total_stmt) or 0)

    rows_raw = list(db.execute(base_stmt.offset(offset).limit(limit)).all())
    rows = [(row[0], int(row[1])) for row in rows_raw]
    return rows, total


def get_event_or_404(db: Session, event_id: str) -> Event:
    stmt = select(Event).where(Event.id == event_id, Event.is_active.is_(True))
    event = db.scalar(stmt)
    if not event:
        raise AppError(
            code=ErrorCodes.EVENT_NOT_FOUND,
            message="Evento no encontrado",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"event_id": event_id},
        )
    return event


def get_event_with_score_or_404(db: Session, event_id: str) -> tuple[Event, int]:
    score_sq = _score_subquery()
    stmt = (
        select(Event, func.coalesce(score_sq.c.score, 0).label("score"))
        .outerjoin(score_sq, score_sq.c.event_id == Event.id)
        .where(Event.id == event_id, Event.is_active.is_(True))
    )
    row = db.execute(stmt).first()
    if not row:
        raise AppError(
            code=ErrorCodes.EVENT_NOT_FOUND,
            message="Evento no encontrado",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"event_id": event_id},
        )
    return row[0], int(row[1])


def create_event(db: Session, payload: EventCreate, current_user: CurrentUser) -> Event:
    category = db.get(Category, payload.category_id)
    if not category:
        raise AppError(
            code=ErrorCodes.CATEGORY_INVALID,
            message="La categoría indicada no existe",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"category_id": payload.category_id},
        )

    # Validar comunidad si se proporciona
    community: Community | None = None
    if payload.community_id:
        community = db.query(Community).filter(
            Community.id == payload.community_id,
            Community.is_active == True,  # noqa: E712
            Community.status == CommunityStatus.ACTIVE,
        ).first()
        if not community:
            raise AppError(
                code=ErrorCodes.COMMUNITY_NOT_ACTIVE,
                message="La comunidad no existe o no está activa",
                status_code=status.HTTP_400_BAD_REQUEST,
                details={"community_id": payload.community_id},
            )

    image_url = payload.image_url
    promoted_key: str | None = None

    incoming_key = extract_file_key_from_public_url(payload.image_url)
    if incoming_key and is_pending_key(incoming_key):
        promoted_key = promote_pending_object(incoming_key)
        image_url = build_public_url(promoted_key)

    event = Event(
        title=payload.title,
        description=payload.description,
        image_url=image_url,
        start_datetime=_coerce_utc(payload.start_datetime),
        end_datetime=_coerce_utc(payload.end_datetime),
        location=payload.location,
        owner_id=current_user.id,
        category_id=payload.category_id,
        social_links=payload.social_links.to_dict() if payload.social_links else None,
    )
    db.add(event)
    db.flush()  # Para obtener el ID antes del commit

    # Crear solicitud de comunidad si se proporcionó
    if community:
        community_request = CommunityEvent(
            community_id=community.id,
            event_id=event.id,
            requested_by=current_user.id,
            status=CommunityEventStatus.PENDING,
        )
        db.add(community_request)

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
    db.refresh(event)
    return event


def _enforce_event_permissions(user: CurrentUser, owner_id: str) -> None:
    if user.id == owner_id:
        return
    if is_admin_role(user.role):
        return
    raise AppError(
        code=ErrorCodes.FORBIDDEN,
        message="No tienes permisos para modificar este evento",
        status_code=status.HTTP_403_FORBIDDEN,
        details={"owner_id": owner_id},
    )


def update_event(db: Session, event: Event, payload: EventUpdate, current_user: CurrentUser) -> Event:
    if not event.is_active:
        raise AppError(
            code=ErrorCodes.EVENT_NOT_FOUND,
            message="Evento no encontrado",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"event_id": event.id},
        )

    _enforce_event_permissions(current_user, event.owner_id)

    data = payload.model_dump(exclude_unset=True)
    if "category_id" in data:
        category = db.get(Category, data["category_id"])
        if not category:
            raise AppError(
                code=ErrorCodes.CATEGORY_INVALID,
                message="La categoría indicada no existe",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                details={"category_id": data["category_id"]},
            )

    # Procesar social_links
    if "social_links" in data and data["social_links"] is not None:
        data["social_links"] = payload.social_links.to_dict()

    if "start_datetime" in data and data["start_datetime"] is not None:
        data["start_datetime"] = _coerce_utc(data["start_datetime"])
    if "end_datetime" in data and data["end_datetime"] is not None:
        data["end_datetime"] = _coerce_utc(data["end_datetime"])

    old_image_key = extract_file_key_from_public_url(event.image_url)
    promoted_new_key: str | None = None
    old_image_to_delete_after_commit: str | None = None

    if "image_url" in data:
        requested_image_url = data["image_url"]
        requested_key = extract_file_key_from_public_url(requested_image_url)

        if requested_key and is_pending_key(requested_key):
            promoted_new_key = promote_pending_object(requested_key)
            data["image_url"] = build_public_url(promoted_new_key)
            if old_image_key and old_image_key != promoted_new_key:
                old_image_to_delete_after_commit = old_image_key
        elif requested_image_url is None:
            if old_image_key:
                old_image_to_delete_after_commit = old_image_key
        elif requested_key and old_image_key and requested_key != old_image_key:
            old_image_to_delete_after_commit = old_image_key

    start = _coerce_utc(data.get("start_datetime", event.start_datetime))
    end = _coerce_utc(data.get("end_datetime", event.end_datetime))
    if end <= start:
        raise AppError(
            code=ErrorCodes.DATE_RANGE_INVALID,
            message="La fecha de fin debe ser posterior a la fecha de inicio",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"start_datetime": start.isoformat(), "end_datetime": end.isoformat()},
        )

    for key, value in data.items():
        setattr(event, key, value)

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
            # No rompemos la actualizacion del evento por un fallo de limpieza diferida.
            pass

    db.refresh(event)
    return event


def delete_event(db: Session, event: Event, current_user: CurrentUser) -> None:
    if not event.is_active:
        raise AppError(
            code=ErrorCodes.EVENT_NOT_FOUND,
            message="Evento no encontrado",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"event_id": event.id},
        )

    _enforce_event_permissions(current_user, event.owner_id)
    event.is_active = False
    db.commit()


def toggle_favorite(db: Session, event_id: str, current_user: CurrentUser) -> bool:
    _ = get_event_or_404(db, event_id)

    favorite = db.get(EventFavorite, {"user_id": current_user.id, "event_id": event_id})
    if favorite:
        db.execute(
            delete(EventFavorite).where(
                EventFavorite.user_id == current_user.id,
                EventFavorite.event_id == event_id,
            )
        )
        db.commit()
        return False

    db.add(EventFavorite(user_id=current_user.id, event_id=event_id))
    db.commit()
    return True


