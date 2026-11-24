from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.db.session import get_db
from auth.schemas.common import RestResponse
from auth.schemas.verify import VerifyEmailConfirmRequest, VerifyEmailResendRequest
from auth.security.rate_limit import limit_auth_recovery_requests, limit_auth_token_action_requests
from auth.services.verification_service import confirm_email_token, resend_verification_email

router = APIRouter(prefix="/auth/verify/email", tags=["verify"])


@router.post("/resend", response_model=RestResponse)
async def resend(
    req: VerifyEmailResendRequest,
    db: Session = Depends(get_db),
    _: None = Depends(limit_auth_recovery_requests),
):
    await resend_verification_email(db, email=str(req.email).strip())
    return RestResponse(success=True, message="Si el correo existe, se enviará un nuevo enlace.", data=None)


@router.post("/confirm", response_model=RestResponse)
def confirm(
    req: VerifyEmailConfirmRequest,
    db: Session = Depends(get_db),
    _: None = Depends(limit_auth_token_action_requests),
):
    user = confirm_email_token(db, token_str=req.token)
    return RestResponse(success=True, message="Ya puedes utilizar tu cuenta, da clic abajo para iniciar sesión.", data={"user_id": user.id})
