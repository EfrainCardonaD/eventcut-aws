"""add is_active to events for soft delete

Revision ID: 20260330_0002
Revises: 20260329_0002
Create Date: 2026-03-30 00:00:00

"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260330_0002"
down_revision: str | None = "20260329_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # MySQL almacena BOOLEAN como TINYINT(1).
    op.add_column(
        "events",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
    )


def downgrade() -> None:
    op.drop_column("events", "is_active")

