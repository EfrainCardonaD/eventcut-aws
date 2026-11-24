from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiErrorData(BaseModel):
    code: str = Field(..., description="Código estable para manejo en frontend")
    details: Any | None = Field(default=None, description="Detalles opcionales del error")
    trace_id: str = Field(..., description="Identificador de trazabilidad de la request")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    message: str = ""
    data: Optional[T] = None


class ApiErrorResponse(BaseModel):
    success: bool = False
    message: str
    data: ApiErrorData

