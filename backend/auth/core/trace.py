from __future__ import annotations

import uuid

from fastapi import Request

TRACE_HEADER_NAME = "X-Trace-Id"


def get_or_create_trace_id(request: Request) -> str:
    incoming = request.headers.get(TRACE_HEADER_NAME, "").strip()
    if incoming:
        return incoming
    return uuid.uuid4().hex


def get_trace_id(request: Request) -> str:
    trace_id = getattr(request.state, "trace_id", None)
    if isinstance(trace_id, str) and trace_id:
        return trace_id
    return get_or_create_trace_id(request)
