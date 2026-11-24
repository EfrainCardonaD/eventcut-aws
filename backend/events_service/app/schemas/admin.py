from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BanUserRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class BannedUserResponse(BaseModel):
    user_id: str
    reason: str
    banned_by: str
    banned_at: datetime
    is_active: bool = True


class BannedUserListResponse(BaseModel):
    items: list[BannedUserResponse]
    total: int


class UnbanResponse(BaseModel):
    user_id: str
    message: str = "Usuario desbaneado exitosamente"


class AdminEventFilters(BaseModel):
    is_active: bool | None = None
    owner_id: str | None = None
    from_datetime: datetime | None = Field(default=None, alias="from")
    to_datetime: datetime | None = Field(default=None, alias="to")
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    model_config = {"populate_by_name": True}


class CommunityStatusAction(BaseModel):
    action: str = Field(..., pattern="^(ACTIVATE|REJECT)$")
    rejection_reason: str | None = Field(default=None, max_length=500)


class AdminCommunityModerationItem(BaseModel):
    id: str
    name: str
    description: str
    image_url: str | None
    owner_id: str
    contact_email: str
    category_id: int | None
    status: str
    is_accepted_terms: bool
    rejection_reason: str | None
    social_links: dict[str, Any] | None
    is_active: bool
    deactivated_at: datetime | None
    deactivated_by: str | None
    deactivated_reason: str | None
    created_at: datetime
    updated_at: datetime | None


class AdminCommunityModerationListResponse(BaseModel):
    items: list[AdminCommunityModerationItem]
    total: int
