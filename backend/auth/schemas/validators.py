from __future__ import annotations

import re

from pydantic_core import PydanticCustomError


def validate_strong_password(value: str) -> str:
    # Política mínima para reducir riesgo de credenciales débiles.
    if len(value) < 8:
        raise PydanticCustomError("password_too_short", "La contraseña debe tener al menos 8 caracteres")
    if not re.search(r"[A-Z]", value):
        raise PydanticCustomError("password_missing_upper", "La contraseña debe incluir una letra mayúscula")
    if not re.search(r"[a-z]", value):
        raise PydanticCustomError("password_missing_lower", "La contraseña debe incluir una letra minúscula")
    if not re.search(r"\d", value):
        raise PydanticCustomError("password_missing_digit", "La contraseña debe incluir al menos un número")
    if not re.search(r"[^A-Za-z0-9]", value):
        raise PydanticCustomError("password_missing_symbol", "La contraseña debe incluir al menos un símbolo")
    return value

