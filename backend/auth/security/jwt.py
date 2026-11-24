from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt

from auth.core.settings import settings


@dataclass(slots=True)
class TokenPair:
    token: str
    refresh_token: str


def _now() -> datetime:
    return datetime.now(UTC)


def _build_base_claims(user_id: str, token_type: str, ttl: timedelta) -> dict[str, Any]:
    now = _now()
    exp = now + ttl
    return {
        "iss": settings.jwt_issuer,
        "sub": user_id,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": str(uuid4()),
    }


def create_access_token(*, user_id: str, username: str, email: str, role: str) -> str:
    claims = _build_base_claims(user_id, "access", timedelta(minutes=settings.jwt_access_ttl_minutes))
    claims.update(
        {
            "username": username,
            "email": email,
            "role": role,
        }
    )
    return jwt.encode(claims, settings.jwt_secret_key, algorithm="HS256")


def create_refresh_token(*, user_id: str, token_version: int) -> str:
    claims = _build_base_claims(user_id, "refresh", timedelta(days=settings.jwt_refresh_expiration_days))
    claims.update(
        {
            "token_version": token_version,
        }
    )
    return jwt.encode(claims, settings.jwt_secret_key, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=["HS256"],
        issuer=settings.jwt_issuer,
        options={"require": ["exp", "iat", "iss", "sub", "type", "jti"]},
    )


def get_token_type(payload: dict[str, Any]) -> str:
    token_type = payload.get("type")
    if token_type not in {"access", "refresh"}:
        raise ValueError("invalid token type")
    return str(token_type)


def get_token_jti(payload: dict[str, Any]) -> str:
    jti = payload.get("jti")
    if not isinstance(jti, str) or not jti:
        raise ValueError("invalid jti")
    return jti


def get_token_expires_at(payload: dict[str, Any]) -> datetime:
    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise ValueError("invalid exp")
    return datetime.fromtimestamp(exp, tz=UTC)
