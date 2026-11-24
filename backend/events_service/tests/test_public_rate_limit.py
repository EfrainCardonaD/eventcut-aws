from __future__ import annotations

import pytest
from starlette.requests import Request

from events_service.app.core.exceptions import AppError
import events_service.app.security.rate_limit as rate_limit


def _build_request(path: str, forwarded_for: str) -> Request:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "root_path": "",
        "query_string": b"",
        "headers": [(b"x-forwarded-for", forwarded_for.encode("ascii"))],
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }
    return Request(scope)


def test_limit_public_events_reads_blocks_after_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rate_limit, "_limiter", rate_limit.InMemoryRateLimiter())
    monkeypatch.setattr(rate_limit, "_public_read_rule", rate_limit.RateLimitRule(max_requests=2, window_seconds=60))

    request = _build_request("/api/v1/events", "203.0.113.10")
    rate_limit.limit_public_events_reads(request)
    rate_limit.limit_public_events_reads(request)

    with pytest.raises(AppError) as exc:
        rate_limit.limit_public_events_reads(request)

    assert exc.value.status_code == 429
    assert exc.value.code == "TOO_MANY_REQUESTS"
    assert exc.value.details["retry_after_seconds"] >= 1


def test_limit_public_events_reads_isolated_by_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rate_limit, "_limiter", rate_limit.InMemoryRateLimiter())
    monkeypatch.setattr(rate_limit, "_public_read_rule", rate_limit.RateLimitRule(max_requests=1, window_seconds=60))

    list_request = _build_request("/api/v1/events", "203.0.113.11")
    detail_request = _build_request("/api/v1/events/abc", "203.0.113.11")

    rate_limit.limit_public_events_reads(list_request)
    rate_limit.limit_public_events_reads(detail_request)

    with pytest.raises(AppError):
        rate_limit.limit_public_events_reads(list_request)


def test_limit_public_communities_reads_blocks_after_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rate_limit, "_limiter", rate_limit.InMemoryRateLimiter())
    monkeypatch.setattr(rate_limit, "_public_read_rule", rate_limit.RateLimitRule(max_requests=1, window_seconds=60))

    request = _build_request("/api/v1/communities", "203.0.113.12")
    rate_limit.limit_public_communities_reads(request)

    with pytest.raises(AppError) as exc:
        rate_limit.limit_public_communities_reads(request)

    assert exc.value.status_code == 429


def test_limit_public_categories_reads_blocks_after_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rate_limit, "_limiter", rate_limit.InMemoryRateLimiter())
    monkeypatch.setattr(rate_limit, "_public_read_rule", rate_limit.RateLimitRule(max_requests=1, window_seconds=60))

    request = _build_request("/api/v1/categories", "203.0.113.13")
    rate_limit.limit_public_categories_reads(request)

    with pytest.raises(AppError) as exc:
        rate_limit.limit_public_categories_reads(request)

    assert exc.value.status_code == 429


