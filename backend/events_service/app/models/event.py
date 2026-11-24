from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from events_service.app.db.base import Base

if TYPE_CHECKING:
    from events_service.app.models.community_event import CommunityEvent


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("idx_events_dates", "start_datetime", "end_datetime"),
        Index("idx_events_category_date", "category_id", "start_datetime"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    title: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    start_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    location: Mapped[str] = mapped_column(String(200), nullable=False)

    owner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("1"))

    # Auditoría de desactivación (baneos / moderación / limpieza)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deactivated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    deactivated_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    social_links: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    community_events: Mapped[list["CommunityEvent"]] = relationship(
        "CommunityEvent",
        back_populates="event",
        cascade="all, delete-orphan",
    )

