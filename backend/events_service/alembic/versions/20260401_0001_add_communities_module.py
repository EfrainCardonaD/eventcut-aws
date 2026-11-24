"""add communities module and social links

Revision ID: 20260401_0001
Revises: 20260330_0002
Create Date: 2026-04-01 00:00:00

"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260401_0001"
down_revision: str | None = "20260330_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # 1. Crear tabla communities
    op.create_table(
        "communities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("image_url", sa.String(255), nullable=True),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("contact_email", sa.String(255), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "ACTIVE", "REJECTED", name="community_status"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("is_accepted_terms", sa.Boolean, nullable=False),
        sa.Column("rejection_reason", sa.String(500), nullable=True),
        sa.Column("social_links", sa.JSON, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("idx_communities_owner_id", "communities", ["owner_id"])
    op.create_index("idx_communities_status", "communities", ["status"])
    op.create_index("idx_communities_owner_status", "communities", ["owner_id", "status"])

    # 2. Crear tabla community_events (pivote)
    op.create_table(
        "community_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "community_id",
            sa.String(36),
            sa.ForeignKey("communities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "event_id",
            sa.String(36),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("PENDING", "APPROVED", "REJECTED", name="community_event_status"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("requested_by", sa.String(36), nullable=False),
        sa.Column("reviewed_by", sa.String(36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_ce_community_status", "community_events", ["community_id", "status"])
    op.create_index("idx_ce_event", "community_events", ["event_id"])
    op.create_unique_constraint("uq_community_event", "community_events", ["community_id", "event_id"])

    # 3. Crear tabla banned_users
    op.create_table(
        "banned_users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), nullable=False, unique=True),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("banned_by", sa.String(36), nullable=False),
        sa.Column("banned_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("1")),
    )
    op.create_index("idx_banned_users_active", "banned_users", ["user_id", "is_active"])

    # 4. Añadir social_links a events
    op.add_column("events", sa.Column("social_links", sa.JSON, nullable=True))


def downgrade() -> None:
    op.drop_column("events", "social_links")
    op.drop_index("idx_banned_users_active", table_name="banned_users")
    op.drop_table("banned_users")
    op.drop_index("idx_ce_event", table_name="community_events")
    op.drop_index("idx_ce_community_status", table_name="community_events")
    op.drop_constraint("uq_community_event", "community_events", type_="unique")
    op.drop_table("community_events")
    op.drop_index("idx_communities_owner_status", table_name="communities")
    op.drop_index("idx_communities_status", table_name="communities")
    op.drop_index("idx_communities_owner_id", table_name="communities")
    op.drop_table("communities")

    # Eliminar ENUMs en MySQL no es necesario, pero para PostgreSQL:
    # op.execute("DROP TYPE IF EXISTS community_status")
    # op.execute("DROP TYPE IF EXISTS community_event_status")
