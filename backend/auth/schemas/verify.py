from __future__ import annotations

from pydantic import BaseModel, EmailStr


class VerifyEmailResendRequest(BaseModel):
    email: EmailStr


class VerifyEmailConfirmRequest(BaseModel):
    token: str

