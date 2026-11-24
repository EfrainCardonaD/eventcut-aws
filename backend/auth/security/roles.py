from __future__ import annotations

from typing import Final

ROLE_PREFIX: Final[str] = "ROLE_"

SYSTEM_ROLES: Final[tuple[str, ...]] = (
    "ROLE_USER",
    "ROLE_ADMIN",
    "ROLE_SUPER_ADMIN",
    "ROLE_SECURITY_ADMIN",
    "ROLE_OPERATOR",
    "ROLE_DEVICE",

)


def normalize_role(role: str) -> str:
    normalized = role.strip().upper()
    if not normalized.startswith(ROLE_PREFIX):
        normalized = f"{ROLE_PREFIX}{normalized}"
    return normalized


def is_valid_role(role: str) -> bool:
    return normalize_role(role) in SYSTEM_ROLES

