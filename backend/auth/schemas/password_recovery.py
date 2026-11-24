from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

from auth.schemas.validators import validate_strong_password


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=16, max_length=255)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _validate_new_password(cls, value: str) -> str:
        return validate_strong_password(value)
