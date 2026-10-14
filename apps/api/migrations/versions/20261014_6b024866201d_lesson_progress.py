"""lesson_event_clock and reading_position: progress that never moves backwards (P11.S2.T1, LESSON-PROGRESS-01)

New tables only; nothing existing changes, so the previous build is unaffected (it neither reads nor writes them).

Revision ID: 6b024866201d
Revises: 910fd1af7ed6
Create Date: 2026-10-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "6b024866201d"
down_revision = "910fd1af7ed6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lesson_event_clock",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("client_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["item_id"], ["content_item.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("user_id", "item_id"),
    )
    op.create_table(
        "reading_position",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("chapter_id", sa.UUID(), nullable=False),
        sa.Column("lesson_id", sa.UUID(), nullable=False),
        sa.Column("block_index", sa.SmallInteger(), nullable=False),
        sa.Column("client_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapter.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["lesson_id"], ["content_item.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("user_id", "chapter_id"),
    )


def downgrade() -> None:
    op.drop_table("reading_position")
    op.drop_table("lesson_event_clock")
