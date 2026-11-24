from __future__ import annotations

from typing import Final

ROLE_PREFIX: Final[str] = "ROLE_"

ROLE_USER: Final[str] = "ROLE_USER"
ROLE_ADMIN: Final[str] = "ROLE_ADMIN"
ROLE_SECURITY_ADMIN: Final[str] = "ROLE_SECURITY_ADMIN"


ADMIN_ROLES: Final[set[str]] = {ROLE_ADMIN, ROLE_SECURITY_ADMIN}


def normalize_role(role: str) -> str:
    normalized = role.strip().upper()
    if not normalized.startswith(ROLE_PREFIX):
        normalized = f"{ROLE_PREFIX}{normalized}"
    return normalized


def is_admin_role(role: str) -> bool:
    return normalize_role(role) in ADMIN_ROLES

