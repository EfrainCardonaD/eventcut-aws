from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import status

from events_service.app.core.exceptions import AppError, ErrorCodes
from events_service.app.core.settings import settings
from events_service.app.schemas.auth import CurrentUser


class AuthGatewayClient:
    def __init__(self) -> None:
        base_urls = settings.parsed_auth_service_base_urls()
        self._base_urls = base_urls if base_urls else [settings.auth_service_base_url.rstrip("/")]

    def fetch_current_user(self, token: str) -> CurrentUser:
        last_error: Exception | None = None
        for base_url in self._base_urls:
            url = f"{base_url}/api/internal/auth/me"
            req = Request(
                url=url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Gateway-Secret": settings.app_gateway_secret,
                    # Evita HTML warning de ngrok en algunos escenarios/proxies.
                    "ngrok-skip-browser-warning": "true",
                },
                method="GET",
            )

            try:
                with urlopen(req, timeout=5.0) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                try:
                    return CurrentUser(
                        id=str(payload["id"]),
                        username=str(payload["username"]),
                        email=str(payload["email"]),
                        role=str(payload["role"]),
                    )
                except Exception as exc:
                    raise AppError(
                        code=ErrorCodes.AUTH_UNAVAILABLE,
                        message="No se pudo validar el usuario (respuesta inválida del servicio de autenticación).",
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        details={"url": url},
                    ) from exc
            except HTTPError as exc:
                if exc.code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_404_NOT_FOUND):
                    raise AppError(
                        code=ErrorCodes.TOKEN_INVALID,
                        message="Token inválido",
                        status_code=status.HTTP_401_UNAUTHORIZED,
                    ) from exc
                last_error = exc
                continue
            except URLError as exc:
                last_error = exc
                continue
            except json.JSONDecodeError as exc:
                raise AppError(
                    code=ErrorCodes.AUTH_UNAVAILABLE,
                    message="No se pudo validar el usuario (respuesta inválida del servicio de autenticación).",
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    details={"url": url},
                ) from exc

        raise AppError(
            code=ErrorCodes.AUTH_UNAVAILABLE,
            message="El servicio de autenticación no está disponible para validar tu sesión.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"last_error": str(last_error) if last_error else None},
        ) from last_error

    def fetch_user_name(self, user_id: str) -> tuple[str, str] | None:
        last_error: Exception | None = None
        for base_url in self._base_urls:
            url = f"{base_url}/api/internal/users/{user_id}"
            req = Request(
                url=url,
                headers={
                    "X-Gateway-Secret": settings.app_gateway_secret,
                    # Evita HTML warning de ngrok en algunos escenarios/proxies.
                    "ngrok-skip-browser-warning": "true",
                },
                method="GET",
            )

            try:
                with urlopen(req, timeout=5.0) as response:
                    payload = json.loads(response.read().decode("utf-8"))

                first_name = payload.get("first_name") or payload.get("firstName")
                last_name = payload.get("last_name") or payload.get("lastName")
                if not isinstance(first_name, str) or not isinstance(last_name, str):
                    raise AppError(
                        code=ErrorCodes.AUTH_UNAVAILABLE,
                        message="No se pudo obtener el owner del evento (respuesta inválida del servicio de autenticación).",
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        details={"url": url, "user_id": user_id},
                    )
                return first_name, last_name
            except HTTPError as exc:
                if exc.code == status.HTTP_404_NOT_FOUND:
                    return None
                last_error = exc
                continue
            except URLError as exc:
                last_error = exc
                continue
            except json.JSONDecodeError as exc:
                raise AppError(
                    code=ErrorCodes.AUTH_UNAVAILABLE,
                    message="No se pudo obtener el owner del evento (respuesta inválida del servicio de autenticación).",
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    details={"url": url, "user_id": user_id},
                ) from exc

        raise AppError(
            code=ErrorCodes.AUTH_UNAVAILABLE,
            message="El servicio de autenticación no está disponible para obtener los datos del owner del evento.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"last_error": str(last_error) if last_error else None, "user_id": user_id},
        ) from last_error

    def fetch_users_name_map(self, user_ids: set[str]) -> dict[str, tuple[str, str]]:
        normalized_ids = list(dict.fromkeys(user_ids))
        if not normalized_ids:
            return {}

        last_error: Exception | None = None
        query = urlencode({"ids": normalized_ids}, doseq=True)

        for base_url in self._base_urls:
            url = f"{base_url}/api/internal/users/summary?{query}"
            req = Request(
                url=url,
                headers={
                    "X-Gateway-Secret": settings.app_gateway_secret,
                    # Evita HTML warning de ngrok en algunos escenarios/proxies.
                    "ngrok-skip-browser-warning": "true",
                },
                method="GET",
            )

            try:
                with urlopen(req, timeout=5.0) as response:
                    payload = json.loads(response.read().decode("utf-8"))

                if not isinstance(payload, dict):
                    raise AppError(
                        code=ErrorCodes.AUTH_UNAVAILABLE,
                        message="No se pudo obtener owners de eventos (respuesta inválida del servicio de autenticación).",
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        details={"url": url, "count": len(normalized_ids)},
                    )

                result: dict[str, tuple[str, str]] = {}
                for user_id, raw_user in payload.items():
                    if not isinstance(raw_user, dict):
                        continue
                    first_name = raw_user.get("first_name") or raw_user.get("firstName")
                    last_name = raw_user.get("last_name") or raw_user.get("lastName")
                    if isinstance(first_name, str) and isinstance(last_name, str):
                        result[str(user_id)] = (first_name, last_name)
                return result
            except HTTPError as exc:
                last_error = exc
                continue
            except URLError as exc:
                last_error = exc
                continue
            except json.JSONDecodeError as exc:
                raise AppError(
                    code=ErrorCodes.AUTH_UNAVAILABLE,
                    message="No se pudo obtener owners de eventos (respuesta inválida del servicio de autenticación).",
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    details={"url": url, "count": len(normalized_ids)},
                ) from exc

        raise AppError(
            code=ErrorCodes.AUTH_UNAVAILABLE,
            message="El servicio de autenticación no está disponible para obtener los datos de owners de eventos.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"last_error": str(last_error) if last_error else None, "count": len(normalized_ids)},
        ) from last_error


auth_gateway_client = AuthGatewayClient()
