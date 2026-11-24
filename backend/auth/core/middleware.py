from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware

from auth.core.settings import Settings


def setup_middlewares(app: FastAPI, settings: Settings) -> None:
    # Trusted hosts: mitiga ataques por Host header en despliegues con proxy
    hosts = settings.parsed_trusted_hosts()
    if hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)

    # Producción: fuerza TLS si el despliegue no lo resuelve aguas arriba.
    if settings.app_force_https:
        app.add_middleware(HTTPSRedirectMiddleware)

    # CORS al final para envolver el resto de middlewares y conservar headers en errores.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.parsed_cors_allowed_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Trace-Id",
            "ngrok-skip-browser-warning",
        ],
        expose_headers=["X-Trace-Id"],
    )
