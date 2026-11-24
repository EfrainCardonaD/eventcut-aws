from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from events_service.app.db.base import Base

if TYPE_CHECKING:
    from events_service.app.models.community import Community
    from events_service.app.models.event import Event


class CommunityEventStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class CommunityEvent(Base):
    __tablename__ = "community_events"
    __table_args__ = (
        Index("idx_ce_community_status", "community_id", "status"),
        Index("idx_ce_event", "event_id"),
        UniqueConstraint("community_id", "event_id", name="uq_community_event"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    community_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("communities.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )

    status: Mapped[CommunityEventStatus] = mapped_column(
        String(20),
        nullable=False,
        default=CommunityEventStatus.PENDING,
        server_default="PENDING",
    )

    requested_by: Mapped[str] = mapped_column(String(36), nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    community: Mapped["Community"] = relationship("Community", back_populates="community_events")
    event: Mapped["Event"] = relationship("Event", back_populates="community_events")
