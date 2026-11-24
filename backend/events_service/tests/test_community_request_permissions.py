from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Generator, cast

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from events_service.app.core.exceptions import AppError
from events_service.app.db.base import Base
from events_service.app.models import Category, Community, CommunityEvent, CommunityEventStatus, CommunityStatus, Event
from events_service.app.schemas.auth import CurrentUser
from events_service.app.services.community_service import list_community_requests
import events_service.app.api.routes.communities as communities_route


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    LocalSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = LocalSession()
    try:
        category = Category(slug="seguridad", name="Seguridad")
        session.add(category)
        session.flush()

        community = Community(
            name="Comunidad Seguridad",
            description="Comunidad para pruebas de solicitudes",
            image_url="https://cdn.example.com/comunidad/seguridad.png",
            owner_id="community-owner",
            contact_email="owner@community.test",
            status=CommunityStatus.ACTIVE,
            is_accepted_terms=True,
        )
        session.add(community)
        session.flush()

        event_owner_1_event = Event(
            title="OWASP Meetup",
            description="Charla sobre hardening",
            image_url="https://cdn.example.com/events/owasp.png",
            start_datetime=datetime(2026, 4, 20, 10, 0, 0),
            end_datetime=datetime(2026, 4, 20, 12, 0, 0),
            location="Sala A",
            owner_id="event-owner-1",
            category_id=category.id,
        )
        event_owner_2_event = Event(
            title="SecOps Day",
            description="Practicas de observabilidad",
            image_url="https://cdn.example.com/events/secops.png",
            start_datetime=datetime(2026, 4, 21, 10, 0, 0),
            end_datetime=datetime(2026, 4, 21, 12, 0, 0),
            location="Sala B",
            owner_id="event-owner-2",
            category_id=category.id,
        )
        session.add_all([event_owner_1_event, event_owner_2_event])
        session.flush()

        session.add_all(
            [
                CommunityEvent(
                    community_id=community.id,
                    event_id=event_owner_1_event.id,
                    requested_by="event-owner-1",
                    status=CommunityEventStatus.PENDING,
                    created_at=datetime(2026, 4, 17, 11, 2, 18),
                ),
                CommunityEvent(
                    community_id=community.id,
                    event_id=event_owner_2_event.id,
                    requested_by="event-owner-2",
                    status=CommunityEventStatus.REJECTED,
                    reviewed_by="community-owner",
                    reviewed_at=datetime(2026, 4, 17, 11, 2, 49),
                    rejection_reason="No cumple",
                    created_at=datetime(2026, 4, 17, 11, 1, 0),
                ),
            ]
        )
        session.commit()
        yield session
    finally:
        session.close()


def _user(user_id: str) -> CurrentUser:
    return CurrentUser(
        id=user_id,
        username=user_id,
        email=f"{user_id}@test.local",
        role="ROLE_USER",
    )


def test_community_owner_can_list_all_requests(db_session: Session) -> None:
    community = db_session.query(Community).first()
    assert community is not None
    community_obj = cast(Community, cast(object, community))

    requests, total = list_community_requests(db_session, community_obj, _user("community-owner"), limit=20, offset=0)

    assert total == 2
    assert len(requests) == 2
    assert {req.requested_by for req in requests} == {"event-owner-1", "event-owner-2"}


def test_event_owner_can_list_only_their_requests(db_session: Session) -> None:
    community = db_session.query(Community).first()
    assert community is not None
    community_obj = cast(Community, cast(object, community))

    requests, total = list_community_requests(db_session, community_obj, _user("event-owner-1"), limit=20, offset=0)

    assert total == 1
    assert len(requests) == 1
    assert requests[0].requested_by == "event-owner-1"


def test_unrelated_user_cannot_list_community_requests(db_session: Session) -> None:
    community = db_session.query(Community).first()
    assert community is not None
    community_obj = cast(Community, cast(object, community))

    with pytest.raises(AppError) as exc:
        list_community_requests(db_session, community_obj, _user("outsider"), limit=20, offset=0)

    assert exc.value.status_code == 403


def test_get_community_requests_response_includes_review_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 4, 17, 11, 2, 49)
    fake_request = SimpleNamespace(
        id="req-1",
        status="REJECTED",
        requested_by="event-owner-1",
        reviewed_by="community-owner",
        reviewed_at=now,
        rejection_reason="No cumple",
        created_at=datetime(2026, 4, 17, 11, 2, 18),
        event=SimpleNamespace(
            id="event-1",
            title="OWASP Meetup",
            start_datetime=datetime(2026, 4, 20, 10, 0, 0),
            owner_id="event-owner-1",
        ),
    )

    monkeypatch.setattr(
        communities_route,
        "get_community_or_404",
        lambda db, community_id: SimpleNamespace(id=community_id, owner_id="community-owner"),
    )
    monkeypatch.setattr(
        communities_route,
        "list_community_requests",
        lambda db, community, current_user, status_filter=None, limit=20, offset=0: ([fake_request], 1),
    )
    monkeypatch.setattr(
        communities_route,
        "_build_owner_name_index",
        lambda owner_ids: {"event-owner-1": ("Ada", "Lovelace")},
    )

    response = communities_route.get_community_requests(
        community_id="community-1",
        status_filter=None,
        limit=20,
        offset=0,
        db=cast(Session, object()),
        current_user=_user("event-owner-1"),
    )

    assert response.data is not None
    assert response.data.total == 1
    assert response.data.items[0].requested_by == "event-owner-1"
    assert response.data.items[0].reviewed_by == "community-owner"
    assert response.data.items[0].reviewed_at == now
    assert response.data.items[0].rejection_reason == "No cumple"





