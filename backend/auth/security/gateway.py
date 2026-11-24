from __future__ import annotations

from fastapi import Header, HTTPException, status

from auth.core.settings import settings


def require_gateway_secret(x_gateway_secret: str | None = Header(default=None, alias="X-Gateway-Secret")) -> None:
    """Protección para endpoints internos.

    - Si APP_GATEWAY_VALIDATION_ENABLED=false => no valida.
    - Si true => exige X-Gateway-Secret == APP_GATEWAY_SECRET.
    """

    if not settings.app_gateway_validation_enabled:
        return

    if not x_gateway_secret or x_gateway_secret != settings.app_gateway_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid gateway secret")
