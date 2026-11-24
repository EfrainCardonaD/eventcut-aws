from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session
from typing import Any, cast

from events_service.app.core.exceptions import AppError, ErrorCodes
from events_service.app.models.banned_user import BannedUser
from events_service.app.services.ban_propagation_service import propagate_user_ban


def _ensure_uuid(value: str, *, field_name: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError) as exc:
        raise AppError(
            code=ErrorCodes.VALIDATION_ERROR,
            message=f"{field_name} debe ser un UUID valido",
        ) from exc


def is_user_banned(db: Session, user_id: str) -> bool:
    """Verifica si un usuario está en la lista de baneados activos."""
    user_id = _ensure_uuid(user_id, field_name="user_id")
    return db.query(BannedUser).filter(
        BannedUser.user_id == user_id,
        BannedUser.is_active == True,  # noqa: E712
    ).first() is not None


def get_ban_record(db: Session, user_id: str) -> BannedUser | None:
    """Obtiene el registro de baneo activo de un usuario."""
    user_id = _ensure_uuid(user_id, field_name="user_id")
    return db.query(BannedUser).filter(
        BannedUser.user_id == user_id,
        BannedUser.is_active == True,  # noqa: E712
    ).first()


def ban_user(db: Session, user_id: str, reason: str, banned_by: str) -> tuple[BannedUser, dict[str, int]]:
    """
    Banea a un usuario. Si ya existe un registro, lo reactiva.

    Además, propaga el baneo haciendo soft delete de todo lo creado por el usuario.
    Nota: al desbanear NO se reactiva contenido.
    """
    user_id = _ensure_uuid(user_id, field_name="user_id")
    banned_by = _ensure_uuid(banned_by, field_name="banned_by")

    existing = db.query(BannedUser).filter(BannedUser.user_id == user_id).first()

    if existing:
        existing.is_active = True
        existing.reason = reason
        existing.banned_by = banned_by
        propagation = propagate_user_ban(db, user_id=user_id, banned_by=banned_by, reason=reason)
        db.commit()
        db.refresh(existing)
        return existing, propagation

    ban = BannedUser(
        user_id=user_id,
        reason=reason,
        banned_by=banned_by,
    )
    db.add(ban)

    propagation = propagate_user_ban(db, user_id=user_id, banned_by=banned_by, reason=reason)
    db.commit()
    db.refresh(ban)
    return ban, propagation


def unban_user(db: Session, user_id: str) -> bool:
    """
    Desbanea a un usuario (soft delete del baneo).
    Retorna True si se desbaneó, False si no existía baneo activo.
    """
    user_id = _ensure_uuid(user_id, field_name="user_id")
    ban = db.query(BannedUser).filter(
        BannedUser.user_id == user_id,
        BannedUser.is_active == True,  # noqa: E712
    ).first()

    if not ban:
        return False

    ban.is_active = False
    db.commit()
    return True


def list_banned_users(
    db: Session,
    *,
    limit: int = 20,
    offset: int = 0,
    include_inactive: bool = False,
) -> tuple[list[BannedUser], int]:
    """Lista usuarios baneados con paginación."""
    query: Any = db.query(BannedUser)

    if not include_inactive:
        query = query.filter(BannedUser.is_active == True)  # noqa: E712

    total = int(query.count() or 0)
    items_any: Any = query.order_by(BannedUser.banned_at.desc()).offset(offset).limit(limit).all()
    return cast(list[BannedUser], items_any), total
