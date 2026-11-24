from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, update
from sqlalchemy.orm import Session

from events_service.app.models import Community, CommunityEvent, CommunityEventStatus, CommunitySubscription, Event, EventFavorite


def propagate_user_ban(
    db: Session,
    *,
    user_id: str,
    banned_by: str,
    reason: str,
) -> dict[str, int]:
    """Propaga el baneo despublicando (soft delete) *todo* lo creado por el usuario.

    Reglas (según negocio):
    - NO se reactiva nada al desbanear.
    - Eventos y comunidades del usuario pasan a `is_active = False`.
    - Solicitudes/relaciones creadas por el usuario se invalidan:
        - CommunityEvent donde `requested_by=user_id` y esté en estado PENDING => REJECTED.
    - Interacciones del usuario (no contenido) se limpian para seguridad/UX:
        - favorites y subscriptions se eliminan.

    Retorna conteos por entidad para auditoría/respuesta del endpoint admin.
    """

    now = datetime.now()

    # 1) Soft delete de eventos
    event_update = (
        update(Event)
        .where(Event.owner_id == user_id, Event.is_active.is_(True))
        .values(
            is_active=False,
            deactivated_at=now,
            deactivated_by=banned_by,
            deactivated_reason=func.concat("BANNED_USER: ", reason),
        )
    )
    event_result = db.execute(event_update)
    events_deactivated = int(getattr(event_result, "rowcount", 0) or 0)

    # 2) Soft delete de comunidades
    community_update = (
        update(Community)
        .where(Community.owner_id == user_id, Community.is_active.is_(True))
        .values(
            is_active=False,
            deactivated_at=now,
            deactivated_by=banned_by,
            deactivated_reason=func.concat("BANNED_USER: ", reason),
        )
    )
    community_result = db.execute(community_update)
    communities_deactivated = int(getattr(community_result, "rowcount", 0) or 0)

    # 3) Invalidar solicitudes creadas por el usuario (solo PENDING)
    request_update = (
        update(CommunityEvent)
        .where(
            CommunityEvent.requested_by == user_id,
            CommunityEvent.status == CommunityEventStatus.PENDING,
        )
        .values(
            status=CommunityEventStatus.REJECTED,
            reviewed_by=banned_by,
            reviewed_at=now,
            rejection_reason=func.concat("BANNED_USER: ", reason),
        )
    )
    request_result = db.execute(request_update)
    requests_rejected = int(getattr(request_result, "rowcount", 0) or 0)

    # 4) Limpieza de interacciones
    favorites_result = db.execute(delete(EventFavorite).where(EventFavorite.user_id == user_id))
    favorites_deleted = int(getattr(favorites_result, "rowcount", 0) or 0)

    subscriptions_result = db.execute(delete(CommunitySubscription).where(CommunitySubscription.user_id == user_id))
    subscriptions_deleted = int(getattr(subscriptions_result, "rowcount", 0) or 0)

    return {
        "events_deactivated": events_deactivated,
        "communities_deactivated": communities_deactivated,
        "requests_rejected": requests_rejected,
        "favorites_deleted": favorites_deleted,
        "subscriptions_deleted": subscriptions_deleted,
    }

