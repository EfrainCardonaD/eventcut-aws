from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from events_service.app.db.base import Base


class BannedUser(Base):
    __tablename__ = "banned_users"
    __table_args__ = (Index("idx_banned_users_active", "user_id", "is_active"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    banned_by: Mapped[str] = mapped_column(String(36), nullable=False)

    banned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("1"))
