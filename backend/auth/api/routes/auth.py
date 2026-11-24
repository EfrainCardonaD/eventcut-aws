from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.db.session import get_db
from auth.models.user import User
from auth.schemas.auth import LoginRequest, RegisterRequest, RegisterResponseData, TokenPairData
from auth.schemas.common import RestResponse
from auth.schemas.user import CurrentUser, UserResponse
from auth.security.dependencies import (
    get_current_token_payload,
    get_current_user,
    get_refresh_token_payload,
    oauth2_scheme,
)
from auth.security.rate_limit import limit_auth_login_requests
from auth.services import auth_service
from auth.services.verification_service import create_or_replace_email_token, send_verification_email

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=RestResponse[RegisterResponseData],
    status_code=status.HTTP_201_CREATED,
)
async def register(req: RegisterRequest, db: Session = Depends(get_db)):
    user = auth_service.register_user(db, req)

    token = create_or_replace_email_token(db, user=user)
    try:
        await send_verification_email(user=user, token=token.token)
    except Exception:
        # No bloqueamos registro por fallos temporales de correo.
        pass

    return RestResponse(
        success=True,
        message="Usuario registrado. Revisa tu correo para verificar tu cuenta.",
        data=RegisterResponseData(id=user.id, username=user.username, email=user.email),
    )


@router.post("/login", response_model=RestResponse[TokenPairData])
def login(
    req: LoginRequest,
    db: Session = Depends(get_db),
    _: None = Depends(limit_auth_login_requests),
):
    user = auth_service.authenticate_user(db, req.username, req.password)
    pair = auth_service.issue_token_pair(user)

    return RestResponse(
        success=True,
        message="Inicio de sesión exitoso",
        data=TokenPairData(
            token=pair.token,
            refreshToken=pair.refresh_token,
            user=UserResponse.from_user(user),
        ),
    )


@router.post("/refresh", response_model=RestResponse[TokenPairData])
def refresh(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
    _payload: dict[str, object] = Depends(get_refresh_token_payload),
):
    pair = auth_service.refresh_tokens(db, token)

    user_id_obj = _payload.get("sub")
    if not isinstance(user_id_obj, str) or not user_id_obj:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Refresh token inválido")

    stmt = select(User).where(User.id == user_id_obj)
    user = db.scalar(stmt)
    # refresh_tokens ya validó el usuario, pero lo recalculamos para armar respuesta.
    # Si el usuario ya no existe, devolvemos error consistente.
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuario no encontrado")

    return RestResponse(
        success=True,
        message="Token renovado exitosamente",
        data=TokenPairData(
            token=pair.token,
            refreshToken=pair.refresh_token,
            user=UserResponse.from_user(user),
        ),
    )


@router.post("/logout", response_model=RestResponse)
def logout(
    db: Session = Depends(get_db),
    payload: dict[str, object] = Depends(get_current_token_payload),
):
    auth_service.revoke_token_payload(db, payload, reason="logout")
    return RestResponse(success=True, message="Sesión cerrada exitosamente", data=None)


@router.get("/me", response_model=RestResponse[CurrentUser])
def me(current_user: CurrentUser = Depends(get_current_user)):
    return RestResponse(
        success=True,
        message="Usuario autenticado",
        data=current_user,
    )

