from __future__ import annotations

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from events_service.app.core.exceptions import AppError, ErrorCodes
from events_service.app.models.category import Category
from events_service.app.models.event import Event
from events_service.app.schemas.category import CategoryCreate, CategoryUpdate


def list_categories(db: Session) -> list[Category]:
    stmt = select(Category).order_by(Category.name.asc())
    return list(db.scalars(stmt).all())


def get_category_or_404(db: Session, category_id: int) -> Category:
    stmt = select(Category).where(Category.id == category_id)
    category = db.scalar(stmt)
    if not category:
        raise AppError(
            code=ErrorCodes.CATEGORY_NOT_FOUND,
            message="Categoría no encontrada",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"category_id": category_id},
        )
    return category


def _assert_unique_fields(
    db: Session,
    *,
    name: str,
    slug: str,
    exclude_id: int | None = None,
) -> None:
    name_stmt = select(Category.id).where(func.lower(Category.name) == name.lower())
    slug_stmt = select(Category.id).where(Category.slug == slug)

    if exclude_id is not None:
        name_stmt = name_stmt.where(Category.id != exclude_id)
        slug_stmt = slug_stmt.where(Category.id != exclude_id)

    if db.scalar(name_stmt) is not None:
        raise AppError(
            code=ErrorCodes.CATEGORY_DUPLICATE,
            message="Ya existe una categoría con ese nombre",
            status_code=status.HTTP_409_CONFLICT,
            details={"name": name},
        )

    if db.scalar(slug_stmt) is not None:
        raise AppError(
            code=ErrorCodes.CATEGORY_DUPLICATE,
            message="Ya existe una categoría con ese slug",
            status_code=status.HTTP_409_CONFLICT,
            details={"slug": slug},
        )


def create_category(db: Session, payload: CategoryCreate) -> Category:
    candidate_name = payload.name.strip()
    candidate_slug = payload.slug or payload.name

    # Reusa la validación de schema para normalizar cuando slug no se envía explícitamente.
    normalized = CategoryCreate(name=candidate_name, slug=candidate_slug)
    _assert_unique_fields(db, name=normalized.name, slug=normalized.slug or "")

    category = Category(name=normalized.name, slug=normalized.slug or "")
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def update_category(db: Session, category: Category, payload: CategoryUpdate) -> Category:
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return category

    next_name = data.get("name", category.name)
    next_slug = data.get("slug", category.slug)

    _assert_unique_fields(db, name=next_name, slug=next_slug, exclude_id=category.id)

    category.name = next_name
    category.slug = next_slug
    db.commit()
    db.refresh(category)
    return category


def delete_category(db: Session, category: Category) -> None:
    in_use_stmt = select(func.count()).select_from(Event).where(Event.category_id == category.id)
    in_use_total = int(db.scalar(in_use_stmt) or 0)
    if in_use_total > 0:
        raise AppError(
            code=ErrorCodes.CATEGORY_IN_USE,
            message="No se puede eliminar una categoría con eventos asociados",
            status_code=status.HTTP_409_CONFLICT,
            details={"category_id": category.id, "events_count": in_use_total},
        )

    db.delete(category)
    db.commit()

