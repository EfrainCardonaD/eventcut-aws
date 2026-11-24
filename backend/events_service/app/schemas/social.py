from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class SocialLinks(BaseModel):
    """Links a redes sociales para eventos y comunidades."""

    whatsapp: str | None = Field(default=None, max_length=255)
    facebook: str | None = Field(default=None, max_length=255)
    instagram: str | None = Field(default=None, max_length=255)

    @staticmethod
    def _normalize_optional_link(v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.strip()
        return cleaned or None

    @field_validator("whatsapp")
    @classmethod
    def validate_whatsapp(cls, v: str | None) -> str | None:
        v = cls._normalize_optional_link(v)
        if v is None:
            return v
        if not v.startswith(("https://wa.me/", "https://chat.whatsapp.com/")):
            raise ValueError("WhatsApp link debe iniciar con https://wa.me/ o https://chat.whatsapp.com/")
        return v

    @field_validator("facebook")
    @classmethod
    def validate_facebook(cls, v: str | None) -> str | None:
        v = cls._normalize_optional_link(v)
        if v is None:
            return v
        if not v.startswith(("https://facebook.com/", "https://www.facebook.com/")):
            raise ValueError("Facebook link debe iniciar con https://facebook.com/ o https://www.facebook.com/")
        return v

    @field_validator("instagram")
    @classmethod
    def validate_instagram(cls, v: str | None) -> str | None:
        v = cls._normalize_optional_link(v)
        if v is None:
            return v
        if not v.startswith(("https://instagram.com/", "https://www.instagram.com/")):
            raise ValueError("Instagram link debe iniciar con https://instagram.com/ o https://www.instagram.com/")
        return v

    def to_dict(self) -> dict | None:
        """Convierte a dict filtrando valores None."""
        data = {k: v for k, v in self.model_dump().items() if v is not None}
        return data if data else None
