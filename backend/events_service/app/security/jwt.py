from __future__ import annotations

from typing import Any, Literal

import jwt

from events_service.app.core.settings import settings

TokenType = Literal["access", "refresh"]


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=["HS256"],
        issuer=settings.jwt_issuer,
        options={"require": ["exp", "iat", "iss", "sub", "jti", "type"]},
    )


def get_token_type(payload: dict[str, Any]) -> TokenType:
    t = payload.get("type")
    if t not in ("access", "refresh"):
        raise ValueError("Invalid token type")
    return t

