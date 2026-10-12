"""study_settings: a learner's usual theme, text size, reduced motion, data saver and video quality (P04.S3.T2,
SETTINGS-01)

Revision ID: a7d3e9f1c258
Revises: f6a1c3e8b204
Create Date: 2026-10-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a7d3e9f1c258"
down_revision = "f6a1c3e8b204"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "study_settings",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("theme", sa.String(length=8), nullable=False),
        sa.Column("text_size", sa.String(length=8), nullable=False),
        sa.Column("reduce_motion", sa.Boolean(), nullable=False),
        sa.Column("data_saver", sa.Boolean(), nullable=False),
        sa.Column("video_quality", sa.String(length=12), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("text_size in ('default','large','larger')", name="study_settings_text_size"),
        sa.CheckConstraint("theme in ('system','light','dark')", name="study_settings_theme"),
        sa.CheckConstraint(
            "video_quality in ('auto','data_saver','standard','high')", name="study_settings_video_quality"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("study_settings")
