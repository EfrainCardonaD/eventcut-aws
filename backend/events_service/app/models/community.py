from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from events_service.app.db.base import Base

if TYPE_CHECKING:
    from events_service.app.models.community_event import CommunityEvent


class CommunityStatus(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"


class Community(Base):
    __tablename__ = "communities"
    __table_args__ = (
        Index("idx_communities_status", "status"),
        Index("idx_communities_owner_status", "owner_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    owner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)

    # Categoría (reutiliza catálogo de categories)
    category_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status: Mapped[CommunityStatus] = mapped_column(
        String(20),
        nullable=False,
        default=CommunityStatus.PENDING,
        server_default="PENDING",
    )
    is_accepted_terms: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    social_links: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("1"))

    # Auditoría de desactivación (baneos / moderación / limpieza)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deactivated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    deactivated_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    community_events: Mapped[list["CommunityEvent"]] = relationship(
        "CommunityEvent",
        back_populates="community",
        cascade="all, delete-orphan",
    )
