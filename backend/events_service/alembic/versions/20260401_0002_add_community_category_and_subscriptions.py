"""add community category and subscriptions

Revision ID: 20260401_0002
Revises: 20260401_0001
Create Date: 2026-04-01 00:10:00

"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260401_0002"
down_revision: str | None = "20260401_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # 1) communities.category_id -> categories.id (nullable por retrocompatibilidad)
    op.add_column("communities", sa.Column("category_id", sa.Integer(), nullable=True))
    op.create_index("idx_communities_category_id", "communities", ["category_id"])
    op.create_foreign_key(
        "fk_communities_category_id",
        source_table="communities",
        referent_table="categories",
        local_cols=["category_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )

    # 2) community_subscriptions
    op.create_table(
        "community_subscriptions",
        sa.Column("user_id", sa.String(36), primary_key=True),
        sa.Column(
            "community_id",
            sa.String(36),
            sa.ForeignKey("communities.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_cs_user_created", "community_subscriptions", ["user_id", "created_at"])
    op.create_index("idx_cs_community", "community_subscriptions", ["community_id"])


def downgrade() -> None:
    op.drop_index("idx_cs_community", table_name="community_subscriptions")
    op.drop_index("idx_cs_user_created", table_name="community_subscriptions")
    op.drop_table("community_subscriptions")

    op.drop_constraint("fk_communities_category_id", "communities", type_="foreignkey")
    op.drop_index("idx_communities_category_id", table_name="communities")
    op.drop_column("communities", "category_id")

