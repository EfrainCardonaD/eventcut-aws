from __future__ import annotations

import jwt as pyjwt
from fastapi import Depends, status
from fastapi.security import OAuth2PasswordBearer

from events_service.app.core.exceptions import AppError, ErrorCodes
from events_service.app.core.settings import settings
from events_service.app.gateway.auth_client import auth_gateway_client
from events_service.app.schemas.auth import CurrentUser
from events_service.app.security.jwt import decode_token, get_token_type

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_token_payload(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = decode_token(token)
    except pyjwt.ExpiredSignatureError:
        raise AppError(code=ErrorCodes.TOKEN_EXPIRED, message="Token expirado", status_code=status.HTTP_401_UNAUTHORIZED)
    except pyjwt.InvalidTokenError:
        raise AppError(code=ErrorCodes.TOKEN_INVALID, message="Token inválido", status_code=status.HTTP_401_UNAUTHORIZED)

    try:
        token_type = get_token_type(payload)
    except ValueError:
        raise AppError(code=ErrorCodes.TOKEN_INVALID, message="Token inválido", status_code=status.HTTP_401_UNAUTHORIZED)

    if token_type != "access":
        raise AppError(
            code=ErrorCodes.TOKEN_INVALID,
            message="Se requiere un access token válido",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    required_claims = ("sub", "username", "email", "role")
    for claim in required_claims:
        value = payload.get(claim)
        if not isinstance(value, str) or not value:
            raise AppError(code=ErrorCodes.TOKEN_INVALID, message="Token inválido", status_code=status.HTTP_401_UNAUTHORIZED)

    return payload


def get_current_user(
    payload: dict = Depends(get_current_token_payload),
    token: str = Depends(oauth2_scheme),
) -> CurrentUser:
    local_user = CurrentUser.from_token_payload(payload)
    if not settings.auth_remote_validation_enabled:
        return local_user
    # Fail-closed: si el auth-service no valida por cualquier motivo, se considera no autenticado.
    return auth_gateway_client.fetch_current_user(token)

