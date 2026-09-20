"""create core user, case, divination and AI interpretation tables

Revision ID: 20260919_0001
Revises:
Create Date: 2026-09-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260919_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id_hash", sa.String(length=128)),
        sa.Column("email", sa.String(length=320)),
        sa.Column("password_hash", sa.String(length=255)),
        sa.Column("display_name", sa.String(length=80)),
        sa.Column("is_anonymous", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("device_id_hash", name="uq_users_device_id_hash"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_device_id_hash", "users", ["device_id_hash"])
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("profile", postgresql.JSONB(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_cases_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_cases"),
        sa.UniqueConstraint("user_id", "client_id", name="uq_cases_user_id"),
    )
    op.create_index("ix_cases_user_updated", "cases", ["user_id", "updated_at"])

    op.create_table(
        "divination_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True)),
        sa.Column("client_record_id", sa.String(length=200), nullable=False),
        sa.Column("method_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("question", postgresql.JSONB()),
        sa.Column("result_payload", postgresql.JSONB(), nullable=False),
        sa.Column("case_snapshot", postgresql.JSONB()),
        sa.Column("algorithm_id", sa.String(length=128), nullable=False),
        sa.Column("algorithm_version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["case_id"], ["cases.id"], name="fk_divination_records_case_id_cases", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_divination_records_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_divination_records"),
        sa.UniqueConstraint(
            "user_id", "client_record_id", name="uq_divination_records_user_id"
        ),
    )
    op.create_index("ix_divination_records_method_type", "divination_records", ["method_type"])
    op.create_index(
        "ix_divination_records_user_created", "divination_records", ["user_id", "created_at"]
    )
    op.create_index(
        "ix_divination_records_type_created", "divination_records", ["method_type", "created_at"]
    )

    op.create_table(
        "ai_interpretations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("provider_id", sa.String(length=128), nullable=False),
        sa.Column("model_id", sa.String(length=255), nullable=False),
        sa.Column("prompt_version", sa.Integer(), nullable=False),
        sa.Column("evidence_method_id", sa.String(length=128), nullable=False),
        sa.Column("answer_style", sa.String(length=32), nullable=False),
        sa.Column("fallback_reason", sa.Text()),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_id", sa.String(length=128)),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["record_id"],
            ["divination_records.id"],
            name="fk_ai_interpretations_record_id_divination_records",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ai_interpretations"),
    )
    op.create_index("ix_ai_interpretations_request_id", "ai_interpretations", ["request_id"])
    op.create_index(
        "ix_ai_interpretations_record_created",
        "ai_interpretations",
        ["record_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("ai_interpretations")
    op.drop_table("divination_records")
    op.drop_table("cases")
    op.drop_table("users")
