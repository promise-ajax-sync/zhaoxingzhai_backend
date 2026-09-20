"""store structured AI readings

Revision ID: 20260919_0002
Revises: 20260919_0001
Create Date: 2026-09-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260919_0002"
down_revision: str | None = "20260919_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_interpretations",
        sa.Column("structured_reading", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_interpretations", "structured_reading")
