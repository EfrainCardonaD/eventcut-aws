from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

from auth.schemas.user import UserResponse
from auth.schemas.validators import validate_strong_password


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(min_length=2, max_length=100)
    last_name: str = Field(min_length=2, max_length=100)

    @field_validator("password")
    @classmethod
    def _password_rules(cls, value: str) -> str:
        return validate_strong_password(value)


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterResponseData(BaseModel):
    id: str
    username: str
    email: EmailStr


class TokenPairData(BaseModel):
    token: str
    refreshToken: str
    user: UserResponse
