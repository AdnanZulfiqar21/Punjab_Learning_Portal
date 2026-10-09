"""lesson completion (P07.S1.T3, LESSON-DONE-01)

Revision ID: f6c1e3a9d572
Revises: e5b0d2f8c461
Create Date: 2026-10-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f6c1e3a9d572"
down_revision = "e5b0d2f8c461"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lesson_completion",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("version_id", sa.UUID(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["item_id"], ["content_item.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["version_id"], ["content_version.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "item_id", name="uq_lesson_completion"),
    )
    op.create_index(op.f("ix_lesson_completion_user_id"), "lesson_completion", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_lesson_completion_user_id"), table_name="lesson_completion")
    op.drop_table("lesson_completion")
