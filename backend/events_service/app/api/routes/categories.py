from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from events_service.app.db.session import get_db
from events_service.app.schemas.auth import CurrentUser
from events_service.app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate
from events_service.app.schemas.common import ApiResponse
from events_service.app.security.admin_required import require_admin
from events_service.app.security.rate_limit import limit_public_categories_reads
from events_service.app.services.category_service import (
    create_category,
    delete_category,
    get_category_or_404,
    list_categories,
    update_category,
)

router = APIRouter(prefix="/v1/categories", tags=["categories"])


@router.get("", response_model=ApiResponse[list[CategoryResponse]])
def get_categories(
    db: Session = Depends(get_db),
    _: None = Depends(limit_public_categories_reads),
) -> ApiResponse[list[CategoryResponse]]:
    categories = list_categories(db)
    data = [CategoryResponse.model_validate(c) for c in categories]
    return ApiResponse(success=True, message="Categorías obtenidas", data=data)


@router.get("/{category_id}", response_model=ApiResponse[CategoryResponse])
def get_category(
    category_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(limit_public_categories_reads),
) -> ApiResponse[CategoryResponse]:
    category = get_category_or_404(db, category_id)
    return ApiResponse(
        success=True,
        message="Categoría obtenida",
        data=CategoryResponse.model_validate(category),
    )


@router.post("", response_model=ApiResponse[CategoryResponse], status_code=status.HTTP_201_CREATED)
def post_category(
    payload: CategoryCreate,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
) -> ApiResponse[CategoryResponse]:
    category = create_category(db, payload)
    return ApiResponse(
        success=True,
        message="Categoría creada",
        data=CategoryResponse.model_validate(category),
    )


@router.patch("/{category_id}", response_model=ApiResponse[CategoryResponse])
def patch_category(
    category_id: int,
    payload: CategoryUpdate,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
) -> ApiResponse[CategoryResponse]:
    category = get_category_or_404(db, category_id)
    updated = update_category(db, category, payload)
    return ApiResponse(
        success=True,
        message="Categoría actualizada",
        data=CategoryResponse.model_validate(updated),
    )


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_category(
    category_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
) -> None:
    category = get_category_or_404(db, category_id)
    delete_category(db, category)


