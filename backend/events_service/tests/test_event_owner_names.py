from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import cast

import events_service.app.api.routes.events as events_route
from sqlalchemy.orm import Session

from events_service.app.core.exceptions import AppError, ErrorCodes
from events_service.app.schemas.auth import CurrentUser


def _event(owner_id: str, event_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=event_id,
        title="Feria Tech",
        description="Networking y charlas",
        image_url="https://cdn.example.com/events/feria-tech.png",
        start_datetime=datetime(2026, 4, 1, 10, 0, 0),
        end_datetime=datetime(2026, 4, 1, 12, 0, 0),
        location="Centro de Convenciones",
        owner_id=owner_id,
        category_id=4,
    )


def test_get_events_includes_owner_first_and_last_name(monkeypatch) -> None:
    rows = [(_event("owner-1", "evt-1"), 2), (_event("owner-1", "evt-2"), 0)]
    calls: list[set[str]] = []

    monkeypatch.setattr(events_route, "list_events", lambda _db, _filters: (rows, len(rows)))

    def _fetch_names(owner_ids: set[str]) -> dict[str, tuple[str, str]]:
        calls.append(owner_ids)
        return {"owner-1": ("Ana", "Lopez")}

    monkeypatch.setattr(events_route.auth_gateway_client, "fetch_users_name_map", _fetch_names)

    response = events_route.get_events(
        category_id=None,
        from_datetime=None,
        to_datetime=None,
        month=None,
        week_start=None,
        sort_by="start_datetime",
        limit=20,
        offset=0,
        db=cast(Session, None),
    )

    assert [item.owner_first_name for item in response.data.items] == ["Ana", "Ana"]
    assert [item.owner_last_name for item in response.data.items] == ["Lopez", "Lopez"]
    # El lookup de owners se hace por lote en una sola llamada.
    assert calls == [{"owner-1"}]


def test_get_events_falls_back_to_none_when_auth_service_fails(monkeypatch) -> None:
    rows = [(_event("owner-2", "evt-3"), 5)]

    monkeypatch.setattr(events_route, "list_events", lambda _db, _filters: (rows, len(rows)))

    def _raise_batch(_owner_ids: set[str]) -> dict[str, tuple[str, str]]:
        raise AppError(
            code=ErrorCodes.AUTH_UNAVAILABLE,
            message="auth down",
            status_code=503,
        )

    def _raise_single(_owner_id: str) -> tuple[str, str] | None:
        raise AppError(
            code=ErrorCodes.AUTH_UNAVAILABLE,
            message="auth down",
            status_code=503,
        )

    monkeypatch.setattr(events_route.auth_gateway_client, "fetch_users_name_map", _raise_batch)
    monkeypatch.setattr(events_route.auth_gateway_client, "fetch_user_name", _raise_single)

    response = events_route.get_events(
        category_id=None,
        from_datetime=None,
        to_datetime=None,
        month=None,
        week_start=None,
        sort_by="start_datetime",
        limit=20,
        offset=0,
        db=cast(Session, None),
    )

    assert response.data.items[0].owner_first_name is None
    assert response.data.items[0].owner_last_name is None


def test_get_my_favorite_events_includes_owner_names(monkeypatch) -> None:
    rows = [(_event("owner-9", "evt-fav-1"), 4)]

    monkeypatch.setattr(events_route, "list_user_favorite_events", lambda _db, _user_id, limit, offset: (rows, 1))
    monkeypatch.setattr(events_route.auth_gateway_client, "fetch_users_name_map", lambda _ids: {"owner-9": ("Luz", "Mora")})

    response = events_route.get_my_favorite_events(
        limit=20,
        offset=0,
        db=cast(Session, None),
        current_user=CurrentUser(id="u-1", username="u1", email="u1@test.com", role="ROLE_USER"),
    )

    assert response.message == "Mis favoritos obtenidos"
    assert response.data.total == 1
    assert response.data.items[0].id == "evt-fav-1"
    assert response.data.items[0].owner_first_name == "Luz"
    assert response.data.items[0].owner_last_name == "Mora"



