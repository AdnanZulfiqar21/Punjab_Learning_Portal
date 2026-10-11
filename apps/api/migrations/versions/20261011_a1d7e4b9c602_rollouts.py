"""feature_rollout: rollout percentage overrides per feature (P16.S3.T1, ROLLOUT-01)

Revision ID: a1d7e4b9c602
Revises: d7a2c5e9f318
Create Date: 2026-10-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a1d7e4b9c602"
down_revision = "d7a2c5e9f318"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feature_rollout",
        sa.Column("key", sa.String(length=40), nullable=False),
        sa.Column("percent", sa.SmallInteger(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("updated_by", sa.UUID(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["updated_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("feature_rollout")
