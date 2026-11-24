from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from auth.security.roles import is_valid_role, normalize_role


class CurrentUser(BaseModel):
    id: str
    username: str
    email: EmailStr
    role: str

    @classmethod
    def from_token_payload(cls, payload: dict) -> "CurrentUser":
        return cls(
            id=str(payload.get("sub")),
            username=str(payload.get("username")),
            email=str(payload.get("email")),
            role=str(payload.get("role")),
        )


class UserResponse(BaseModel):
    id: str
    username: str
    email: EmailStr
    first_name: str
    last_name: str
    role: str
    active: bool
    email_verified: bool
    token_version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_user(cls, user) -> "UserResponse":
        return cls(
            id=str(user.id),
            username=str(user.username),
            email=str(user.email),
            first_name=str(user.first_name),
            last_name=str(user.last_name),
            role=str(user.role),
            active=bool(user.active),
            email_verified=bool(user.email_verified),
            token_version=int(user.token_version),
            created_at=user.created_at,
            updated_at=user.updated_at,
        )


class UserSummaryResponse(BaseModel):
    id: str
    first_name: str
    last_name: str

    @classmethod
    def from_user(cls, user) -> "UserSummaryResponse":
        return cls(id=str(user.id), first_name=str(user.first_name), last_name=str(user.last_name))


class UpdateUserRoleRequest(BaseModel):
    role: str = Field(min_length=4, max_length=50)

    @field_validator("role")
    @classmethod
    def _normalize_role(cls, value: str) -> str:
        normalized = normalize_role(value)
        if not is_valid_role(normalized):
            raise ValueError("Rol no permitido")
        return normalized


class UpdateUserRoleResponse(BaseModel):
    id: str
    role: str
    token_version: int
