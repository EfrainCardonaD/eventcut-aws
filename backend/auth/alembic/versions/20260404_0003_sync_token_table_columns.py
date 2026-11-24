"""sync token table columns with ORM models

Revision ID: 20260404_0003
Revises: 20260328_0002
Create Date: 2026-04-04

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260404_0003"
down_revision = "20260328_0002"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_column("reset_tokens", "attempts"):
        op.add_column(
            "reset_tokens",
            sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        )

    if not _has_column("reset_tokens", "created_at"):
        op.add_column(
            "reset_tokens",
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    if not _has_column("reset_tokens", "updated_at"):
        op.add_column(
            "reset_tokens",
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    if not _has_column("verification_tokens", "created_at"):
        op.add_column(
            "verification_tokens",
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    if not _has_column("verification_tokens", "updated_at"):
        op.add_column(
            "verification_tokens",
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )


def downgrade() -> None:
    if _has_column("verification_tokens", "updated_at"):
        op.drop_column("verification_tokens", "updated_at")

    if _has_column("verification_tokens", "created_at"):
        op.drop_column("verification_tokens", "created_at")

    if _has_column("reset_tokens", "updated_at"):
        op.drop_column("reset_tokens", "updated_at")

    if _has_column("reset_tokens", "created_at"):
        op.drop_column("reset_tokens", "created_at")

    if _has_column("reset_tokens", "attempts"):
        op.drop_column("reset_tokens", "attempts")

