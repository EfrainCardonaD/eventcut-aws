"""add indexes for ban propagation

Revision ID: 20260401_0003
Revises: 20260401_0002
Create Date: 2026-04-01 01:00:00

"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260401_0003"
down_revision: str | None = "20260401_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Optimizan updates masivos por owner/requested_by durante propagación de baneos.
    op.create_index("idx_events_owner_active", "events", ["owner_id", "is_active"])
    op.create_index("idx_communities_owner_active", "communities", ["owner_id", "is_active"])
    op.create_index("idx_ce_requested_by_status", "community_events", ["requested_by", "status"])


def downgrade() -> None:
    op.drop_index("idx_ce_requested_by_status", table_name="community_events")
    op.drop_index("idx_communities_owner_active", table_name="communities")
    op.drop_index("idx_events_owner_active", table_name="events")

