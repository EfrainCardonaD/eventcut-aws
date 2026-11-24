from __future__ import annotations

from datetime import datetime, timedelta
from typing import Generator

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from events_service.app.core.exceptions import AppError
from events_service.app.db.base import Base
from events_service.app.models.category import Category
from events_service.app.models.event import Event
from events_service.app.models.event_favorite import EventFavorite
from events_service.app.schemas.auth import CurrentUser
from events_service.app.schemas.event import EventCreate
from events_service.app.schemas.event import EventUpdate
from events_service.app.services.event_service import (
    create_event,
    delete_event,
    get_event_or_404,
    list_user_favorite_events,
    toggle_favorite,
    update_event,
)
import events_service.app.services.event_service as event_service


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    LocalSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = LocalSession()
    try:
        category = Category(slug="ingenieria", name="Ingenieria")
        session.add(category)
        session.flush()

        event = Event(
            title="Taller de Arquitectura",
            description="Sesion tecnica para backend y eventos",
            image_url="https://cdn.example.com/events/taller-arq.png",
            start_datetime=datetime(2026, 4, 1, 9, 0, 0),
            end_datetime=datetime(2026, 4, 1, 11, 0, 0),
            location="Auditorio Principal",
            owner_id="owner-1",
            category_id=category.id,
        )
        session.add(event)
        session.commit()
        yield session
    finally:
        session.close()


def test_non_owner_non_admin_cannot_update_event(db_session: Session) -> None:
    event = db_session.scalar(select(Event).where(Event.owner_id == "owner-1"))
    assert event is not None

    outsider = CurrentUser(id="user-2", username="user2", email="u2@test.com", role="ROLE_USER")
    payload = EventUpdate(title="Cambio no permitido")

    with pytest.raises(AppError) as exc:
        update_event(db_session, event, payload, outsider)

    assert exc.value.status_code == 403


def test_security_admin_can_update_event(db_session: Session) -> None:
    event = db_session.scalar(select(Event).where(Event.owner_id == "owner-1"))
    assert event is not None

    admin = CurrentUser(id="sec-admin", username="secadmin", email="sa@test.com", role="ROLE_SECURITY_ADMIN")
    payload = EventUpdate(location="Laboratorio 2")

    updated = update_event(db_session, event, payload, admin)
    assert updated.location == "Laboratorio 2"


def test_favorite_toggle_insert_then_delete(db_session: Session) -> None:
    event = db_session.scalar(select(Event).where(Event.owner_id == "owner-1"))
    assert event is not None

    viewer = CurrentUser(id="user-9", username="viewer", email="viewer@test.com", role="ROLE_USER")

    first_toggle = toggle_favorite(db_session, event.id, viewer)
    assert first_toggle is True
    count_after_insert = db_session.scalar(select(EventFavorite).where(EventFavorite.user_id == viewer.id))
    assert count_after_insert is not None

    second_toggle = toggle_favorite(db_session, event.id, viewer)
    assert second_toggle is False
    count_after_delete = db_session.scalar(select(EventFavorite).where(EventFavorite.user_id == viewer.id))
    assert count_after_delete is None


def test_list_user_favorite_events_returns_only_active_for_user_and_sorted(db_session: Session) -> None:
    base_event = db_session.scalar(select(Event).where(Event.owner_id == "owner-1"))
    assert base_event is not None

    second_event = Event(
        title="Demo UX Mobile",
        description="Sesion para pruebas cross-device",
        image_url="https://cdn.example.com/events/demo-ux-mobile.png",
        start_datetime=datetime(2026, 4, 2, 9, 0, 0),
        end_datetime=datetime(2026, 4, 2, 11, 0, 0),
        location="Laboratorio B",
        owner_id="owner-2",
        category_id=base_event.category_id,
        is_active=True,
    )
    inactive_event = Event(
        title="Evento archivado",
        description="No debe mostrarse en favoritos",
        image_url="https://cdn.example.com/events/archivado.png",
        start_datetime=datetime(2026, 4, 3, 10, 0, 0),
        end_datetime=datetime(2026, 4, 3, 12, 0, 0),
        location="Sala C",
        owner_id="owner-3",
        category_id=base_event.category_id,
        is_active=False,
    )
    db_session.add_all([second_event, inactive_event])
    db_session.flush()

    user_id = "user-sync-1"
    db_session.add_all(
        [
            EventFavorite(user_id=user_id, event_id=base_event.id, created_at=datetime(2026, 4, 5, 0, 16, 5)),
            EventFavorite(user_id=user_id, event_id=second_event.id, created_at=datetime(2026, 4, 5, 0, 20, 0)),
            EventFavorite(user_id=user_id, event_id=inactive_event.id, created_at=datetime(2026, 4, 5, 0, 21, 0)),
            EventFavorite(user_id="other-user", event_id=base_event.id, created_at=datetime(2026, 4, 5, 0, 22, 0)),
        ]
    )
    db_session.commit()

    rows, total = list_user_favorite_events(db_session, user_id, limit=20, offset=0)

    assert total == 2
    assert [event.id for event, _ in rows] == [second_event.id, base_event.id]


def test_update_rejects_invalid_time_window(db_session: Session) -> None:
    event = db_session.scalar(select(Event).where(Event.owner_id == "owner-1"))
    assert event is not None

    owner = CurrentUser(id="owner-1", username="owner", email="owner@test.com", role="ROLE_USER")
    payload = EventUpdate(end_datetime=event.start_datetime - timedelta(minutes=5))

    with pytest.raises(AppError) as exc:
        update_event(db_session, event, payload, owner)

    assert exc.value.status_code == 422


def test_create_event_sets_active_by_default(db_session: Session) -> None:
    owner = CurrentUser(id="owner-2", username="owner2", email="owner2@test.com", role="ROLE_USER")
    payload = EventCreate(
        title="Conferencia de Sistemas",
        description="Presentaciones tecnicas del semestre",
        image_url="https://cdn.example.com/events/conferencia-sistemas.png",
        start_datetime=datetime(2026, 4, 2, 10, 0, 0),
        end_datetime=datetime(2026, 4, 2, 12, 0, 0),
        location="Sala Magna",
        category_id=1,
    )

    created = create_event(db_session, payload, owner)
    assert created.is_active is True


def test_delete_event_soft_deletes_and_hides_from_reads(db_session: Session) -> None:
    event = db_session.scalar(select(Event).where(Event.owner_id == "owner-1"))
    assert event is not None

    owner = CurrentUser(id="owner-1", username="owner", email="owner@test.com", role="ROLE_USER")
    delete_event(db_session, event, owner)

    stored = db_session.scalar(select(Event).where(Event.id == event.id))
    assert stored is not None
    assert stored.is_active is False

    with pytest.raises(AppError) as exc:
        get_event_or_404(db_session, event.id)

    assert exc.value.status_code == 404


def test_create_event_promotes_pending_image_before_persist(monkeypatch: pytest.MonkeyPatch, db_session: Session) -> None:
    owner = CurrentUser(id="owner-3", username="owner3", email="owner3@test.com", role="ROLE_USER")
    payload = EventCreate(
        title="Bootcamp de Datos",
        description="Laboratorio de integracion de servicios",
        image_url="https://cdn.example.com/events/pending/new-image.png",
        start_datetime=datetime(2026, 4, 3, 10, 0, 0),
        end_datetime=datetime(2026, 4, 3, 12, 0, 0),
        location="Sala Norte",
        category_id=1,
    )

    monkeypatch.setattr(event_service, "extract_file_key_from_public_url", lambda url: "events/pending/new-image.png")
    monkeypatch.setattr(event_service, "is_pending_key", lambda key: key.startswith("events/pending/"))
    monkeypatch.setattr(event_service, "promote_pending_object", lambda key: "events/new-image.png")
    monkeypatch.setattr(event_service, "build_public_url", lambda key: f"https://cdn.example.com/{key}")

    created = create_event(db_session, payload, owner)
    assert created.image_url == "https://cdn.example.com/events/new-image.png"


def test_update_event_replaces_image_and_deletes_previous_after_commit(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    event = db_session.scalar(select(Event).where(Event.owner_id == "owner-1"))
    assert event is not None
    owner = CurrentUser(id="owner-1", username="owner", email="owner@test.com", role="ROLE_USER")
    payload = EventUpdate(image_url="https://cdn.example.com/events/pending/replacement.png")

    deleted_keys: list[str] = []

    def _extract(url: str | None) -> str | None:
        if not url:
            return None
        marker = "https://cdn.example.com/"
        if url.startswith(marker):
            return url[len(marker) :]
        return None

    monkeypatch.setattr(event_service, "extract_file_key_from_public_url", _extract)
    monkeypatch.setattr(event_service, "is_pending_key", lambda key: key.startswith("events/pending/"))
    monkeypatch.setattr(event_service, "promote_pending_object", lambda key: "events/replacement.png")
    monkeypatch.setattr(event_service, "build_public_url", lambda key: f"https://cdn.example.com/{key}")
    monkeypatch.setattr(event_service, "delete_object", lambda key: deleted_keys.append(key))

    updated = update_event(db_session, event, payload, owner)
    assert updated.image_url == "https://cdn.example.com/events/replacement.png"
    assert deleted_keys == ["events/taller-arq.png"]


def test_update_event_cleans_promoted_image_when_commit_fails(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    event = db_session.scalar(select(Event).where(Event.owner_id == "owner-1"))
    assert event is not None
    owner = CurrentUser(id="owner-1", username="owner", email="owner@test.com", role="ROLE_USER")
    payload = EventUpdate(image_url="https://cdn.example.com/events/pending/fail.png")

    deleted_keys: list[str] = []

    def _extract(url: str | None) -> str | None:
        if not url:
            return None
        marker = "https://cdn.example.com/"
        if url.startswith(marker):
            return url[len(marker) :]
        return None

    original_commit = db_session.commit

    monkeypatch.setattr(event_service, "extract_file_key_from_public_url", _extract)
    monkeypatch.setattr(event_service, "is_pending_key", lambda key: key.startswith("events/pending/"))
    monkeypatch.setattr(event_service, "promote_pending_object", lambda key: "events/fail.png")
    monkeypatch.setattr(event_service, "build_public_url", lambda key: f"https://cdn.example.com/{key}")
    monkeypatch.setattr(event_service, "delete_object", lambda key: deleted_keys.append(key))

    state = {"count": 0}

    def _failing_commit() -> None:
        state["count"] += 1
        if state["count"] == 1:
            raise RuntimeError("db down")
        original_commit()

    monkeypatch.setattr(db_session, "commit", _failing_commit)

    with pytest.raises(RuntimeError):
        update_event(db_session, event, payload, owner)

    assert deleted_keys == ["events/fail.png"]


