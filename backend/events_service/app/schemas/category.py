from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _slugify(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9\s-]", "", normalized)
    normalized = re.sub(r"[\s_-]+", "-", normalized)
    return normalized.strip("-")


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str


class CategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    slug: str | None = Field(default=None, min_length=2, max_length=50)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("El nombre de la categoría es obligatorio")
        return cleaned

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = _slugify(v)
        if not cleaned:
            raise ValueError("El slug de la categoría es inválido")
        return cleaned


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=50)
    slug: str | None = Field(default=None, min_length=2, max_length=50)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("El nombre de la categoría es obligatorio")
        return cleaned

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = _slugify(v)
        if not cleaned:
            raise ValueError("El slug de la categoría es inválido")
        return cleaned


