from __future__ import annotations

import pytest
from fastapi import HTTPException
from pydantic_core import PydanticCustomError

from auth.schemas.validators import validate_strong_password
from auth.security import dependencies as security_deps
from auth.security.dependencies import get_current_token_payload, get_current_user, require_roles
from auth.security.roles import is_valid_role, normalize_role


class _FakeUser:
    def __init__(self, role: str) -> None:
        self.role = role


def test_validate_strong_password_ok() -> None:
    assert validate_strong_password("Segura2026!") == "Segura2026!"


def test_validate_strong_password_missing_symbol() -> None:
    with pytest.raises(PydanticCustomError):
        validate_strong_password("Segura2026")


def test_normalize_role_and_valid_roles() -> None:
    assert normalize_role("admin") == "ROLE_ADMIN"
    assert is_valid_role("ROLE_ADMIN") is True
    assert is_valid_role("ROLE_UNKNOWN") is False


def test_require_roles_allows_authorized_user() -> None:
    dep = require_roles("admin", "security_admin")
    user = _FakeUser(role="ROLE_ADMIN")
    assert dep(user) is user


def test_require_roles_rejects_unauthorized_user() -> None:
    dep = require_roles("ROLE_ADMIN")
    user = _FakeUser(role="ROLE_USER")

    with pytest.raises(HTTPException) as exc:
        dep(user)

    assert exc.value.status_code == 403


def test_get_current_token_payload_requires_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        security_deps,
        "decode_token",
        lambda _token: {"type": "access", "sub": "u-1", "username": "ana", "email": "ana@test.com"},
    )

    with pytest.raises(HTTPException) as exc:
        get_current_token_payload(token="fake")

    assert exc.value.status_code == 401


def test_get_current_user_builds_current_user_from_token(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "type": "access",
        "sub": "u-1",
        "username": "ana",
        "email": "ana@test.com",
        "role": "ROLE_ADMIN",
    }
    monkeypatch.setattr(security_deps, "decode_token", lambda _token: payload)

    token_payload = get_current_token_payload(token="fake")
    current_user = get_current_user(token_payload)

    assert current_user.id == "u-1"
    assert current_user.username == "ana"
    assert current_user.email == "ana@test.com"
    assert current_user.role == "ROLE_ADMIN"

