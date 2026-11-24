from __future__ import annotations

from fastapi import Depends, status

from events_service.app.core.exceptions import AppError, ErrorCodes
from events_service.app.schemas.auth import CurrentUser
from events_service.app.security.dependencies import get_current_user
from events_service.app.security.roles import is_admin_role


def require_admin(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """
    Valida que el usuario tenga rol de administrador.
    Lanza excepción 403 si no tiene rol ROLE_ADMIN o ROLE_SECURITY_ADMIN.
    """
    if not is_admin_role(current_user.role):
        raise AppError(
            code=ErrorCodes.FORBIDDEN,
            message="Se requieren permisos de administrador",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return current_user
