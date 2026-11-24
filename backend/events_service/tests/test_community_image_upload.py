from __future__ import annotations

from typing import Generator

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import events_service.app.api.routes.communities as communities_route
import events_service.app.schemas.community as community_schema
import events_service.app.services.community_service as community_service
from events_service.app.db.base import Base
from events_service.app.models.community import Community, CommunityStatus
from events_service.app.schemas.auth import CurrentUser
from events_service.app.schemas.community import CommunityCreate, CommunityUpdate
from events_service.app.services.community_service import create_community, update_community


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    local_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = local_session()
    try:
        community = Community(
            name="Comunidad Backend",
            description="Espacio para talleres de arquitectura",
            image_url="https://cdn.example.com/comunidad/old.png",
            owner_id="owner-1",
            contact_email="owner1@test.com",
            status=CommunityStatus.ACTIVE,
            is_accepted_terms=True,
        )
        session.add(community)
        session.commit()
        yield session
    finally:
        session.close()


def test_create_community_promotes_pending_image_before_persist(monkeypatch: pytest.MonkeyPatch, db_session: Session) -> None:
    monkeypatch.setattr(community_schema, "R2_PUBLIC_HOST", "https://cdn.example.com")
    owner = CurrentUser(id="owner-2", username="owner2", email="owner2@test.com", role="ROLE_USER")
    payload = CommunityCreate(
        name="Comunidad Data",
        description="Encuentros de ciencia de datos aplicada",
        image_url="https://cdn.example.com/comunidad/pending/new-image.png",
        contact_email="contacto-data@test.com",
        is_accepted_terms=True,
    )

    monkeypatch.setattr(community_service, "extract_file_key_from_public_url", lambda url: "comunidad/pending/new-image.png")
    monkeypatch.setattr(
        community_service,
        "is_pending_key",
        lambda key, namespace=None: namespace == "comunidad" and key.startswith("comunidad/pending/"),
    )
    monkeypatch.setattr(
        community_service,
        "promote_pending_object",
        lambda key, namespace=None: "comunidad/new-image.png",
    )
    monkeypatch.setattr(community_service, "build_public_url", lambda key: f"https://cdn.example.com/{key}")

    created = create_community(db_session, payload, owner)
    assert created.image_url == "https://cdn.example.com/comunidad/new-image.png"


def test_update_community_replaces_image_and_deletes_previous_after_commit(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    monkeypatch.setattr(community_schema, "R2_PUBLIC_HOST", "https://cdn.example.com")
    community = db_session.scalar(select(Community).where(Community.owner_id == "owner-1"))
    assert community is not None

    owner = CurrentUser(id="owner-1", username="owner", email="owner@test.com", role="ROLE_USER")
    payload = CommunityUpdate(image_url="https://cdn.example.com/comunidad/pending/replacement.png")

    deleted_keys: list[str] = []

    def _extract(url: str | None) -> str | None:
        if not url:
            return None
        marker = "https://cdn.example.com/"
        if url.startswith(marker):
            return url[len(marker) :]
        return None

    monkeypatch.setattr(community_service, "extract_file_key_from_public_url", _extract)
    monkeypatch.setattr(
        community_service,
        "is_pending_key",
        lambda key, namespace=None: namespace == "comunidad" and key.startswith("comunidad/pending/"),
    )
    monkeypatch.setattr(
        community_service,
        "promote_pending_object",
        lambda key, namespace=None: "comunidad/replacement.png",
    )
    monkeypatch.setattr(community_service, "build_public_url", lambda key: f"https://cdn.example.com/{key}")
    monkeypatch.setattr(community_service, "delete_object", lambda key: deleted_keys.append(key))

    updated = update_community(db_session, community, payload, owner)
    assert updated.image_url == "https://cdn.example.com/comunidad/replacement.png"
    assert deleted_keys == ["comunidad/old.png"]


def test_get_community_image_upload_url_uses_comunidad_namespace(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    def _fake_generate_presigned_upload_url(*, content_type: str, namespace: str) -> dict:
        calls.append((content_type, namespace))
        return {
            "upload_url": "https://upload.example.com/put",
            "file_key": "comunidad/pending/demo.png",
            "public_url": "https://cdn.example.com/comunidad/pending/demo.png",
        }

    monkeypatch.setattr(communities_route, "generate_presigned_upload_url", _fake_generate_presigned_upload_url)

    user = CurrentUser(id="owner-9", username="owner9", email="owner9@test.com", role="ROLE_USER")
    response = communities_route.get_community_image_upload_url(content_type="image/png", current_user=user)

    assert response.success is True
    assert response.data["file_key"].startswith("comunidad/pending/")
    assert calls == [("image/png", "comunidad")]

