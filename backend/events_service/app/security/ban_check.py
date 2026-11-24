from __future__ import annotations

from fastapi import Depends, status
from sqlalchemy.orm import Session

from events_service.app.core.exceptions import AppError, ErrorCodes
from events_service.app.db.session import get_db
from events_service.app.schemas.auth import CurrentUser
from events_service.app.security.dependencies import get_current_user
from events_service.app.services.ban_service import is_user_banned


def check_user_not_banned(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """
    Verifica que el usuario actual no esté baneado.
    Lanza excepción 403 si el usuario está en la lista de baneados activos.

    Usar como dependencia en endpoints de escritura (POST, PATCH, DELETE).
    """
    if is_user_banned(db, current_user.id):
        raise AppError(
            code=ErrorCodes.USER_BANNED,
            message="Tu cuenta ha sido suspendida. Contacta soporte para más información.",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    return current_user


# Alias para uso semántico en endpoints
get_verified_user = check_user_not_banned
