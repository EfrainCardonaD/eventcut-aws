from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from events_service.app.db.base import Base


class CommunitySubscription(Base):
    __tablename__ = "community_subscriptions"
    __table_args__ = (
        Index("idx_cs_user_created", "user_id", "created_at"),
        Index("idx_cs_community", "community_id"),
    )

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    community_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("communities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

