from __future__ import annotations

from typing import Callable

import jwt as pyjwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.db.session import get_db
from auth.models.revoked_token import RevokedToken
from auth.schemas.user import CurrentUser
from auth.security.jwt import decode_token, get_token_expires_at, get_token_jti, get_token_type
from auth.security.roles import normalize_role

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def _is_token_revoked(db: Session, jti: str) -> bool:
    # Conservador: si existe en tabla => revocado
    stmt = select(RevokedToken.jti).where(RevokedToken.jti == jti)
    return db.scalar(stmt) is not None


def get_current_token_payload(
    token: str = Depends(oauth2_scheme),
) -> dict:
    try:
        payload = decode_token(token)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    try:
        token_type = get_token_type(payload)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    if token_type != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Se requiere access token")

    required_claims = ("sub", "username", "email", "role")
    for claim in required_claims:
        value = payload.get(claim)
        if not isinstance(value, str) or not value:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    return payload


def get_current_user(
    payload: dict = Depends(get_current_token_payload),
) -> CurrentUser:
    return CurrentUser.from_token_payload(payload)


def require_roles(*roles: str) -> Callable[..., CurrentUser]:
    required = {normalize_role(role) for role in roles}

    def _dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if normalize_role(user.role) not in required:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")
        return user

    return _dep


def get_refresh_token_payload(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> dict:
    # Reutilizamos oauth2_scheme para leer Authorization: Bearer <refresh>
    try:
        payload = decode_token(token)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expirado")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido")

    jti = get_token_jti(payload)
    if _is_token_revoked(db, jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revocado")

    try:
        token_type = get_token_type(payload)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido")

    if token_type != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Se requiere refresh token")

    # exp es validado por decode_token
    _ = get_token_expires_at(payload)
    return payload

