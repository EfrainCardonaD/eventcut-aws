from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request, status

from auth.core.settings import settings


@dataclass(frozen=True)
class RateLimitRule:
    max_requests: int
    window_seconds: int


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def hit(self, key: str, rule: RateLimitRule) -> tuple[bool, int]:
        now = monotonic()
        cutoff = now - float(rule.window_seconds)

        with self._lock:
            bucket = self._buckets[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= rule.max_requests:
                retry_after = max(1, int((bucket[0] + rule.window_seconds) - now))
                return False, retry_after

            bucket.append(now)
            return True, 0


_limiter = InMemoryRateLimiter()
_login_rule = RateLimitRule(
    max_requests=max(1, settings.auth_login_rate_limit_requests),
    window_seconds=max(1, settings.auth_login_rate_limit_window_seconds),
)
_recovery_rule = RateLimitRule(
    max_requests=max(1, settings.auth_recovery_rate_limit_requests),
    window_seconds=max(1, settings.auth_recovery_rate_limit_window_seconds),
)
_token_action_rule = RateLimitRule(
    max_requests=max(1, settings.auth_token_action_rate_limit_requests),
    window_seconds=max(1, settings.auth_token_action_rate_limit_window_seconds),
)


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        first = forwarded_for.split(",", maxsplit=1)[0].strip()
        if first:
            return first

    if request.client and request.client.host:
        return request.client.host

    return "unknown"


def _enforce(request: Request, namespace: str, rule: RateLimitRule) -> None:
    key = f"{namespace}:{_client_ip(request)}:{request.url.path}"
    allowed, retry_after = _limiter.hit(key, rule)
    if allowed:
        return

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Demasiadas solicitudes. Intenta nuevamente en {retry_after} segundos.",
    )


def limit_auth_login_requests(request: Request) -> None:
    _enforce(request, "auth-login", _login_rule)


def limit_auth_recovery_requests(request: Request) -> None:
    _enforce(request, "auth-recovery", _recovery_rule)


def limit_auth_token_action_requests(request: Request) -> None:
    _enforce(request, "auth-token-action", _token_action_rule)

