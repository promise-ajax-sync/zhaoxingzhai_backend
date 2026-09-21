"""add optimistic sync versions

Revision ID: 20260921_0006
Revises: 20260920_0005
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260921_0006"
down_revision: str | None = "20260920_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cases",
        sa.Column("sync_version", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "divination_records",
        sa.Column("sync_version", sa.Integer(), server_default="1", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("divination_records", "sync_version")
    op.drop_column("cases", "sync_version")
