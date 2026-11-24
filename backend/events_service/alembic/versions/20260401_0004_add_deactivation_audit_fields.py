"""add deactivation audit fields for soft delete

Revision ID: 20260401_0004
Revises: 20260401_0003
Create Date: 2026-04-01 01:20:00

"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260401_0004"
down_revision: str | None = "20260401_0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # events: auditoría
    op.add_column("events", sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("events", sa.Column("deactivated_by", sa.String(36), nullable=True))
    op.add_column("events", sa.Column("deactivated_reason", sa.String(500), nullable=True))

    # communities: auditoría
    op.add_column("communities", sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("communities", sa.Column("deactivated_by", sa.String(36), nullable=True))
    op.add_column("communities", sa.Column("deactivated_reason", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("communities", "deactivated_reason")
    op.drop_column("communities", "deactivated_by")
    op.drop_column("communities", "deactivated_at")

    op.drop_column("events", "deactivated_reason")
    op.drop_column("events", "deactivated_by")
    op.drop_column("events", "deactivated_at")

