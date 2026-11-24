from __future__ import annotations

import pytest
from fastapi import HTTPException

from auth.core.settings import settings
from auth.security.gateway import require_gateway_secret


def test_gateway_secret_disabled_allows_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_gateway_validation_enabled", False)
    require_gateway_secret(x_gateway_secret=None)


def test_gateway_secret_enabled_rejects_missing_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_gateway_validation_enabled", True)
    monkeypatch.setattr(settings, "app_gateway_secret", "expected")

    with pytest.raises(HTTPException) as exc:
        require_gateway_secret(x_gateway_secret=None)

    assert exc.value.status_code == 401


def test_gateway_secret_enabled_accepts_valid_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_gateway_validation_enabled", True)
    monkeypatch.setattr(settings, "app_gateway_secret", "expected")

    require_gateway_secret(x_gateway_secret="expected")
