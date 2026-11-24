from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from events_service.app.core.trace import TRACE_HEADER_NAME, get_or_create_trace_id


class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.trace_id = get_or_create_trace_id(request)
        response: Response = await call_next(request)
        response.headers[TRACE_HEADER_NAME] = request.state.trace_id
        return response

