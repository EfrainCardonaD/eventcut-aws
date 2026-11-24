from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import auth.security.rate_limit as rate_limit


def _build_request(path: str, forwarded_for: str) -> Request:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "root_path": "",
        "query_string": b"",
        "headers": [(b"x-forwarded-for", forwarded_for.encode("ascii"))],
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }
    return Request(scope)


def test_login_rate_limit_blocks_after_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rate_limit, "_limiter", rate_limit.InMemoryRateLimiter())
    monkeypatch.setattr(rate_limit, "_login_rule", rate_limit.RateLimitRule(max_requests=1, window_seconds=60))

    req = _build_request("/api/auth/login", "198.51.100.10")
    rate_limit.limit_auth_login_requests(req)

    with pytest.raises(HTTPException) as exc:
        rate_limit.limit_auth_login_requests(req)

    assert exc.value.status_code == 429


def test_recovery_rate_limit_blocks_after_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rate_limit, "_limiter", rate_limit.InMemoryRateLimiter())
    monkeypatch.setattr(rate_limit, "_recovery_rule", rate_limit.RateLimitRule(max_requests=1, window_seconds=60))

    req = _build_request("/api/auth/password/forgot", "198.51.100.11")
    rate_limit.limit_auth_recovery_requests(req)

    with pytest.raises(HTTPException) as exc:
        rate_limit.limit_auth_recovery_requests(req)

    assert exc.value.status_code == 429


def test_token_action_rate_limit_blocks_after_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rate_limit, "_limiter", rate_limit.InMemoryRateLimiter())
    monkeypatch.setattr(rate_limit, "_token_action_rule", rate_limit.RateLimitRule(max_requests=1, window_seconds=60))

    req = _build_request("/api/auth/verify/email/confirm", "198.51.100.12")
    rate_limit.limit_auth_token_action_requests(req)

    with pytest.raises(HTTPException) as exc:
        rate_limit.limit_auth_token_action_requests(req)

    assert exc.value.status_code == 429

