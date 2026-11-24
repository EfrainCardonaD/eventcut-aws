from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.db.session import get_db
from auth.schemas.common import RestResponse
from auth.schemas.password_recovery import ForgotPasswordRequest, ResetPasswordRequest
from auth.security.rate_limit import limit_auth_recovery_requests, limit_auth_token_action_requests
from auth.services.password_recovery_service import forgot_password, reset_password

router = APIRouter(prefix="/auth/password", tags=["password-recovery"])


@router.post("/forgot", response_model=RestResponse)
async def post_forgot_password(
    req: ForgotPasswordRequest,
    db: Session = Depends(get_db),
    _: None = Depends(limit_auth_recovery_requests),
):
    await forgot_password(db, email=req.email)
    return RestResponse(success=True, message="Si el correo existe, se enviará un enlace de recuperación.", data=None)


@router.post("/reset", response_model=RestResponse)
def post_reset_password(
    req: ResetPasswordRequest,
    db: Session = Depends(get_db),
    _: None = Depends(limit_auth_token_action_requests),
):
    reset_password(db, token=req.token, new_password=req.new_password)
    return RestResponse(success=True, message="Contraseña actualizada", data=None)
