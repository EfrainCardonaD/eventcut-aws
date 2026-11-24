from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Error de dominio/aplicación."""

    def __init__(self, code: str, message: str, status_code: int = 400, details: Any | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


class ErrorCodes:
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    AUTH_UNAVAILABLE = "AUTH_UNAVAILABLE"
    TOKEN_INVALID = "TOKEN_INVALID"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    USER_BANNED = "USER_BANNED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    EVENT_NOT_FOUND = "EVENT_NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"
