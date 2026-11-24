from __future__ import annotations

import os
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from events_service.app.schemas.rich_text import sanitize_basic_rich_text
from events_service.app.schemas.social import SocialLinks
from events_service.app.services.storage_service import get_public_host

S3_PUBLIC_HOST = os.getenv("AWS_S3_PUBLIC_HOST") or os.getenv("R2_PUBLIC_HOST")
R2_PUBLIC_HOST = S3_PUBLIC_HOST


def _get_allowed_community_hosts() -> list[str]:
    candidates = [R2_PUBLIC_HOST, S3_PUBLIC_HOST, get_public_host()]
    return [(h or "").rstrip("/") for h in candidates if h]


class CommunityCreate(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    description: str = Field(min_length=5, max_length=2000)
    image_url: str | None = Field(default=None, max_length=255)
    contact_email: EmailStr
    category_id: int | None = Field(default=None, ge=1)
    is_accepted_terms: bool
    social_links: SocialLinks | None = None

    @field_validator("image_url")
    @classmethod
    def validate_image_source(cls, value: str | None) -> str | None:
        if value is None:
            return value

        allowed_hosts = _get_allowed_community_hosts()
        if allowed_hosts and not any(value.startswith(host + "/") for host in allowed_hosts):
            raise ValueError("La imagen debe estar alojada en el dominio autorizado del sistema.")
        return value

    @field_validator("description")
    @classmethod
    def sanitize_description(cls, value: str) -> str:
        return sanitize_basic_rich_text(value)


class CommunityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=100)
    description: str | None = Field(default=None, min_length=5, max_length=2000)
    image_url: str | None = Field(default=None, max_length=255)
    contact_email: EmailStr | None = None
    category_id: int | None = Field(default=None, ge=1)
    social_links: SocialLinks | None = None

    @field_validator("image_url")
    @classmethod
    def validate_image_source(cls, value: str | None) -> str | None:
        if value is None:
            return value

        allowed_hosts = _get_allowed_community_hosts()
        if allowed_hosts and not any(value.startswith(host + "/") for host in allowed_hosts):
            raise ValueError("La imagen debe estar alojada en el dominio autorizado del sistema.")
        return value

    @field_validator("description")
    @classmethod
    def sanitize_description(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return sanitize_basic_rich_text(value)


class CommunityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    image_url: str | None
    owner_id: str
    owner_first_name: str | None = None
    owner_last_name: str | None = None
    contact_email: str
    category_id: int | None = None
    status: str
    social_links: dict | None = None
    events_count: int = 0
    created_at: datetime


class CommunityListResponse(BaseModel):
    items: list[CommunityResponse]
    total: int


class CommunityPublicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    image_url: str | None
    owner_id: str
    owner_first_name: str | None = None
    owner_last_name: str | None = None
    contact_email: str
    category_id: int | None = None
    status: str
    social_links: dict | None = None
    events_count: int = 0
    created_at: datetime


class CommunityPublicListResponse(BaseModel):
    items: list[CommunityPublicResponse]
    total: int


class CommunityEventRequestCreate(BaseModel):
    """Para crear una solicitud de evento a comunidad."""
    pass  # No requiere body, se infiere de la URL


class CommunityEventRequestResponse(BaseModel):
    request_id: str
    community_id: str
    event_id: str
    status: str
    requested_by: str
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None
    created_at: datetime


class CommunityEventRequestAction(BaseModel):
    action: Literal["APPROVE", "REJECT"]
    rejection_reason: str | None = Field(default=None, max_length=500)


class CommunityEventRequestEventSummary(BaseModel):
    id: str
    title: str
    start_datetime: datetime
    owner_id: str
    owner_first_name: str | None = None
    owner_last_name: str | None = None


class CommunityEventRequestListItem(BaseModel):
    request_id: str
    event: CommunityEventRequestEventSummary
    status: str
    requested_by: str
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None
    created_at: datetime


class CommunityEventRequestListResponse(BaseModel):
    items: list[CommunityEventRequestListItem]
    total: int


class CommunityScheduleResponse(BaseModel):
    community: dict
    items: list[dict]
    total: int
