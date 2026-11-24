from __future__ import annotations

from sqlalchemy.orm import Session

from events_service.app.models import CommunitySubscription
from events_service.app.schemas.auth import CurrentUser
from events_service.app.services.community_service import get_active_community_or_404


def subscribe_to_community(db: Session, community_id: str, current_user: CurrentUser) -> None:
    """Suscribe al usuario actual a una comunidad.

    Idempotente: si ya existe la suscripción, no falla.
    """
    community = get_active_community_or_404(db, community_id)

    existing = (
        db.query(CommunitySubscription)
        .filter(
            CommunitySubscription.user_id == current_user.id,
            CommunitySubscription.community_id == community.id,
        )
        .first()
    )
    if existing:
        return

    db.add(CommunitySubscription(user_id=current_user.id, community_id=community.id))
    db.commit()


def unsubscribe_from_community(db: Session, community_id: str, current_user: CurrentUser) -> None:
    """Elimina la suscripción del usuario actual a una comunidad.

    Idempotente: si no existe, no falla.
    """
    subscription = (
        db.query(CommunitySubscription)
        .filter(
            CommunitySubscription.user_id == current_user.id,
            CommunitySubscription.community_id == community_id,
        )
        .first()
    )

    if subscription is None:
        return

    db.delete(subscription)
    db.commit()


def list_subscribed_communities(
    db: Session,
    current_user: CurrentUser,
    *,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[str], int]:
    """Lista IDs de comunidades a las que el usuario está suscrito.

    Devolvemos IDs para que la capa de rutas pueda construir la respuesta completa
    (incluyendo owner names) reutilizando el builder existente.
    """

    query = db.query(CommunitySubscription.community_id).filter(CommunitySubscription.user_id == current_user.id)

    total = query.count()
    rows: list[tuple[str]] = query.order_by(CommunitySubscription.created_at.desc()).offset(offset).limit(limit).all()
    return [community_id for (community_id,) in rows], total


