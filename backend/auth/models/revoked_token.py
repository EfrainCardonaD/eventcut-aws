from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from auth.db.base import Base


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    # jti del JWT; suficiente como PK para lookup rápido
    jti: Mapped[str] = mapped_column(String(64), primary_key=True)

    # para housekeeping / auditoría
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(String(50), nullable=False, default="logout")

