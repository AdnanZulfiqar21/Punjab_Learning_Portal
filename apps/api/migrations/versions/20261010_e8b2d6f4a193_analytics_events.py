"""analytics_event (P16.S2.T1, ANALYTICS-EVENTS-01)

Revision ID: e8b2d6f4a193
Revises: d7a1c5e9f382
Create Date: 2026-10-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e8b2d6f4a193"
down_revision = "d7a1c5e9f382"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analytics_event",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("version", sa.SmallInteger(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("properties", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analytics_event_name_time", "analytics_event", ["name", "occurred_at"], unique=False)
    op.create_index(op.f("ix_analytics_event_user_id"), "analytics_event", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_analytics_event_user_id"), table_name="analytics_event")
    op.drop_index("ix_analytics_event_name_time", table_name="analytics_event")
    op.drop_table("analytics_event")
