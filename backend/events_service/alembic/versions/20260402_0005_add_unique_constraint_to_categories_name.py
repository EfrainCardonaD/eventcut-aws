"""add unique constraint to categories.name

Revision ID: 20260402_0005
Revises: 20260401_0004
Create Date: 2026-04-02 00:00:00

"""

from __future__ import annotations

from typing import Sequence

from alembic import op


revision: str = "20260402_0005"
down_revision: str | None = "20260401_0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint("uq_categories_name", "categories", ["name"])


def downgrade() -> None:
    op.drop_constraint("uq_categories_name", "categories", type_="unique")

