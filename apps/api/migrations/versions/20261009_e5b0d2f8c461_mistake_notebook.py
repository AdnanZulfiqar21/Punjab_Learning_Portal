"""mistake notebook with spaced review (P12.S3, NOTEBOOK-01)

Revision ID: e5b0d2f8c461
Revises: d4a9c1e7b350
Create Date: 2026-10-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e5b0d2f8c461"
down_revision = "d4a9c1e7b350"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mistake_entry",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("family_id", sa.UUID(), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("version_id", sa.UUID(), nullable=False),
        sa.Column("source_attempt_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("grade_number", sa.SmallInteger(), nullable=False),
        sa.Column("subject_code", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("interval_index", sa.SmallInteger(), nullable=False),
        sa.Column("misses", sa.SmallInteger(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_event", sa.String(length=10), nullable=False),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status in ('open','mastered','voided')", name="mistake_entry_status"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["item_id"], ["content_item.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["version_id"], ["content_version.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_attempt_id"], ["attempt.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "family_id", name="uq_mistake_entry_family"),
    )
    op.create_index(op.f("ix_mistake_entry_user_id"), "mistake_entry", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_mistake_entry_user_id"), table_name="mistake_entry")
    op.drop_table("mistake_entry")
