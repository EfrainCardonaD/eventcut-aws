from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock
from time import monotonic

from fastapi import Request, status

from events_service.app.core.exceptions import AppError, ErrorCodes
from events_service.app.core.settings import settings


@dataclass(frozen=True)
class RateLimitRule:
    max_requests: int
    window_seconds: int


class InMemoryRateLimiter:
    """Rate limiter simple por ventana deslizante en memoria por proceso."""

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
_public_read_rule = RateLimitRule(
    max_requests=max(1, settings.public_read_rate_limit_requests),
    window_seconds=max(1, settings.public_read_rate_limit_window_seconds),
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


def _limit_public_reads(request: Request, *, namespace: str) -> None:
    key = f"{namespace}:{_client_ip(request)}:{request.url.path}"
    allowed, retry_after = _limiter.hit(key, _public_read_rule)
    if allowed:
        return

    raise AppError(
        code=ErrorCodes.TOO_MANY_REQUESTS,
        message="Demasiadas solicitudes. Intenta nuevamente en unos segundos.",
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        details={"retry_after_seconds": retry_after, "path": request.url.path},
    )


def limit_public_events_reads(request: Request) -> None:
    _limit_public_reads(request, namespace="events-public")


def limit_public_communities_reads(request: Request) -> None:
    _limit_public_reads(request, namespace="communities-public")


def limit_public_categories_reads(request: Request) -> None:
    _limit_public_reads(request, namespace="categories-public")


