from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Error de dominio/aplicación.

    Nota: se implementa como Exception clásica para no interferir con traceback
    (py3.14+ / contextlib / pytest). Se transforma a HTTP por handlers globales.
    """

    def __init__(self, code: str, message: str, status_code: int = 400, details: Any | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


class ErrorCodes:
    # Auth
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    AUTH_UNAVAILABLE = "AUTH_UNAVAILABLE"
    TOKEN_INVALID = "TOKEN_INVALID"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    # User bans
    USER_BANNED = "USER_BANNED"
    # Validación
    VALIDATION_ERROR = "VALIDATION_ERROR"
    # Dominio eventos
    EVENT_NOT_FOUND = "EVENT_NOT_FOUND"
    CATEGORY_INVALID = "CATEGORY_INVALID"
    CATEGORY_NOT_FOUND = "CATEGORY_NOT_FOUND"
    CATEGORY_DUPLICATE = "CATEGORY_DUPLICATE"
    CATEGORY_IN_USE = "CATEGORY_IN_USE"
    DATE_RANGE_INVALID = "DATE_RANGE_INVALID"
    MONTH_INVALID = "MONTH_INVALID"
    NOT_EVENT_OWNER = "NOT_EVENT_OWNER"
    # Dominio comunidades
    COMMUNITY_NOT_FOUND = "COMMUNITY_NOT_FOUND"
    COMMUNITY_NOT_ACTIVE = "COMMUNITY_NOT_ACTIVE"
    NOT_COMMUNITY_OWNER = "NOT_COMMUNITY_OWNER"
    DUPLICATE_COMMUNITY_NAME = "DUPLICATE_COMMUNITY_NAME"
    EVENT_ALREADY_REQUESTED = "EVENT_ALREADY_REQUESTED"
    REQUEST_NOT_FOUND = "REQUEST_NOT_FOUND"
    TERMS_NOT_ACCEPTED = "TERMS_NOT_ACCEPTED"
    # Storage
    STORAGE_MISCONFIGURED = "STORAGE_MISCONFIGURED"
    STORAGE_UNAVAILABLE = "STORAGE_UNAVAILABLE"
    TOO_MANY_REQUESTS = "TOO_MANY_REQUESTS"
    # Genéricos
    INTERNAL_ERROR = "INTERNAL_ERROR"


