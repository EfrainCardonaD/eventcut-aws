"""reconcile events revision chain

Revision ID: 20260329_0002
Revises: 20260328_0001
Create Date: 2026-03-29 00:00:00

"""
from __future__ import annotations

from typing import Sequence

# revision identifiers, used by Alembic.
revision: str = "20260329_0002"
down_revision: str | None = "20260328_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Revision puente para alinear el historial ya aplicado en BD.
    pass


def downgrade() -> None:
    pass

