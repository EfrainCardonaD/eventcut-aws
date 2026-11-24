from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from events_service.app.models.category import Category


DEFAULT_CATEGORIES = [
    {"slug": "cinecut", "name": "CineCUT"},
    {"slug": "ingenieria", "name": "Ingenieria"},
    {"slug": "deportes", "name": "Deportes"},
    {"slug": "cultura", "name": "Cultura"},
]


def seed_categories(db: Session) -> int:
    created = 0
    for item in DEFAULT_CATEGORIES:
        exists = db.scalar(select(Category.id).where(Category.slug == item["slug"]))
        if exists is not None:
            continue
        db.add(Category(slug=item["slug"], name=item["name"]))
        created += 1

    if created:
        db.commit()
    return created

