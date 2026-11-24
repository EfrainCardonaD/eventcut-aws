from __future__ import annotations

from datetime import datetime
from typing import Generator

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from events_service.app.core.exceptions import AppError, ErrorCodes
from events_service.app.db.base import Base
from events_service.app.models.category import Category
from events_service.app.models.event import Event
from events_service.app.schemas.category import CategoryCreate, CategoryUpdate
from events_service.app.services.category_service import (
    create_category,
    delete_category,
    get_category_or_404,
    list_categories,
    update_category,
)


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    LocalSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = LocalSession()
    try:
        alpha = Category(slug="arte", name="Arte")
        beta = Category(slug="tecnologia", name="Tecnologia")
        session.add_all([beta, alpha])
        session.flush()

        event = Event(
            title="Expo Tecnologia",
            description="Exhibicion de proyectos",
            image_url="https://cdn.example.com/events/expo-tecnologia.png",
            start_datetime=datetime(2026, 5, 1, 10, 0, 0),
            end_datetime=datetime(2026, 5, 1, 12, 0, 0),
            location="Centro de Innovacion",
            owner_id="owner-1",
            category_id=beta.id,
        )
        session.add(event)
        session.commit()
        yield session
    finally:
        session.close()


def test_list_categories_orders_by_name(db_session: Session) -> None:
    categories = list_categories(db_session)
    assert [c.name for c in categories] == ["Arte", "Tecnologia"]


def test_create_category_generates_slug_when_missing(db_session: Session) -> None:
    created = create_category(db_session, CategoryCreate(name="Vida Estudiantil"))

    assert created.name == "Vida Estudiantil"
    assert created.slug == "vida-estudiantil"


def test_create_category_rejects_duplicate_name(db_session: Session) -> None:
    with pytest.raises(AppError) as exc:
        create_category(db_session, CategoryCreate(name="Tecnologia"))

    assert exc.value.code == ErrorCodes.CATEGORY_DUPLICATE
    assert exc.value.status_code == 409


def test_update_category_rejects_duplicate_slug(db_session: Session) -> None:
    category = db_session.scalar(select(Category).where(Category.slug == "arte"))
    assert category is not None

    with pytest.raises(AppError) as exc:
        update_category(db_session, category, CategoryUpdate(slug="tecnologia"))

    assert exc.value.code == ErrorCodes.CATEGORY_DUPLICATE
    assert exc.value.status_code == 409


def test_delete_category_in_use_is_blocked(db_session: Session) -> None:
    category = db_session.scalar(select(Category).where(Category.slug == "tecnologia"))
    assert category is not None

    with pytest.raises(AppError) as exc:
        delete_category(db_session, category)

    assert exc.value.code == ErrorCodes.CATEGORY_IN_USE
    assert exc.value.status_code == 409


def test_delete_category_without_events_succeeds(db_session: Session) -> None:
    category = db_session.scalar(select(Category).where(Category.slug == "arte"))
    assert category is not None

    delete_category(db_session, category)

    deleted = db_session.scalar(select(Category).where(Category.slug == "arte"))
    assert deleted is None

