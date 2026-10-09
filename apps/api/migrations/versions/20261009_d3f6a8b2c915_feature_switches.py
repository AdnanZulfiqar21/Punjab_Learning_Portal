"""feature switches (P17.S3.T3, OPS-01)

Revision ID: d3f6a8b2c915
Revises: 9b5d1f3e7a64
Create Date: 2026-10-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d3f6a8b2c915"
down_revision = "9b5d1f3e7a64"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feature_switch",
        sa.Column("key", sa.String(length=40), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("updated_by", sa.UUID(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["updated_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("feature_switch")
