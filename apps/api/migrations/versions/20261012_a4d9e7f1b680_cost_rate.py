"""cost_rate: unit rates for the cohort economics report, append-only (P16.S2.T4, ECONOMICS-01)

A new table only; nothing existing changes, so the previous build is unaffected.

Revision ID: a4d9e7f1b680
Revises: f3c8d6e0a579
Create Date: 2026-10-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a4d9e7f1b680"
down_revision = "f3c8d6e0a579"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cost_rate",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("key", sa.String(length=40), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("source_note", sa.Text(), nullable=False),
        sa.Column("set_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="cost_rate_currency"),
        sa.CheckConstraint("amount >= 0", name="cost_rate_amount"),
        sa.ForeignKeyConstraint(["set_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cost_rate_current", "cost_rate", ["key", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_cost_rate_current", table_name="cost_rate")
    op.drop_table("cost_rate")
