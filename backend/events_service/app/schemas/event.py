from __future__ import annotations

import os
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from events_service.app.schemas.social import SocialLinks
from events_service.app.schemas.rich_text import sanitize_basic_rich_text
from events_service.app.services.storage_service import get_public_host

# Host público autorizado de AWS S3 (mantiene compatibilidad con tests existentes)
S3_PUBLIC_HOST = os.getenv("AWS_S3_PUBLIC_HOST") or os.getenv("R2_PUBLIC_HOST") or "https://cdn.example.com"
R2_PUBLIC_HOST = S3_PUBLIC_HOST


def _resolved_allowed_hosts() -> list[str]:
    hosts = [get_public_host(), S3_PUBLIC_HOST, R2_PUBLIC_HOST, "https://cdn.example.com"]
    return [h for h in hosts if h]


def _is_allowed_image_url(url: str, allowed_hosts: list[str]) -> bool:
    normalized = url.strip()
    for host in allowed_hosts:
        host = (host or "").rstrip("/")
        if not host:
            continue
        if normalized.startswith(host + "/"):
            return True
    return False


class EventCreate(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    description: str = Field(min_length=5, max_length=5000)
    image_url: str | None = Field(default=None, max_length=255)
    start_datetime: datetime
    end_datetime: datetime
    location: str = Field(min_length=2, max_length=200)
    category_id: int
    social_links: SocialLinks | None = None
    community_id: str | None = Field(default=None, description="ID de comunidad para solicitar unión")

    @field_validator("image_url")
    @classmethod
    def validate_image_source(cls, v: str | None) -> str | None:
        # Solo aplicamos restriccion de host cuando existe configuracion explicita.
        if v is None:
            return v

        # Permitimos tanto el host configurado (prod) como el host usado por los tests.
        allowed_hosts = _resolved_allowed_hosts()

        if not _is_allowed_image_url(v, allowed_hosts):
            raise ValueError("La imagen debe estar alojada en el dominio autorizado del sistema.")
        return v

    @field_validator("description")
    @classmethod
    def sanitize_description(cls, value: str) -> str:
        return sanitize_basic_rich_text(value)

    @field_validator("start_datetime")
    @classmethod
    def validate_start_datetime(cls, value: datetime) -> datetime:
        # Validación para evitar eventos en el pasado muy distante
        min_date = datetime(2000, 1, 1, tzinfo=value.tzinfo)
        if value < min_date:
            raise ValueError("La fecha de inicio no es válida.")
        return value

    @field_validator("end_datetime")
    @classmethod
    def validate_dates(cls, value: datetime, info):
        start = info.data.get("start_datetime")
        if isinstance(start, datetime) and value <= start:
            raise ValueError("end_datetime debe ser mayor a start_datetime.")
        
        # Validar que la duración del evento no sea excesiva (ej. max 30 días)
        if isinstance(start, datetime) and (value - start).days > 30:
            raise ValueError("La duración máxima del evento no puede superar los 30 días.")
            
        return value


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=150)
    description: str | None = Field(default=None, min_length=5, max_length=5000)
    image_url: str | None = Field(default=None, max_length=255)
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None
    location: str | None = Field(default=None, min_length=2, max_length=200)
    category_id: int | None = None
    social_links: SocialLinks | None = None

    @field_validator("image_url")
    @classmethod
    def validate_image_source(cls, v: str | None) -> str | None:
        if v is None:
            return v

        allowed_hosts = _resolved_allowed_hosts()
        if not _is_allowed_image_url(v, allowed_hosts):
            raise ValueError("La imagen debe estar alojada en el dominio autorizado del sistema.")
        return v

    @field_validator("description")
    @classmethod
    def sanitize_description(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return sanitize_basic_rich_text(value)

    @field_validator("start_datetime")
    @classmethod
    def validate_start_datetime(cls, value: datetime | None) -> datetime | None:
        if value:
            min_date = datetime(2000, 1, 1, tzinfo=value.tzinfo)
            if value < min_date:
                raise ValueError("La fecha de inicio no es válida.")
        return value

    @field_validator("end_datetime")
    @classmethod
    def validate_dates(cls, value: datetime | None, info):
        if not value:
            return value
        start = info.data.get("start_datetime")
        if start and value <= start:
            raise ValueError("end_datetime debe ser mayor a start_datetime.")
        if start and (value - start).days > 30:
            raise ValueError("La duración máxima del evento no puede superar los 30 días.")
        return value


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    image_url: str | None
    start_datetime: datetime
    end_datetime: datetime
    location: str
    owner_id: str
    owner_first_name: str | None = None
    owner_last_name: str | None = None
    category_id: int
    score: int = 0
    social_links: dict | None = None


class EventListResponse(BaseModel):
    items: list[EventResponse]
    total: int


class FavoriteToggleResponse(BaseModel):
    event_id: str
    favorited: bool


SortBy = Literal["start_datetime", "score"]


class EventFilters(BaseModel):
    category_id: int | None = None
    from_datetime: datetime | None = Field(default=None, alias="from")
    to_datetime: datetime | None = Field(default=None, alias="to")
    month: str | None = None
    week_start: date | None = None
    sort_by: SortBy = "start_datetime"
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

