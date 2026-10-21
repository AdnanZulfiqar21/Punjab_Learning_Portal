"""Content releases: several items published together, rolled back together (P06.S3.T2, CONTENT-RELEASE-01).

New tables only; the previous build doesn't read them, and single-item publishing is unchanged.

Revision ID: 8d2f6b1e7a30
Revises: 3b7e2a9c4d51
Create Date: 2026-10-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "8d2f6b1e7a30"
down_revision = "3b7e2a9c4d51"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "content_release",
        sa.Column("id", uid, primary_key=True),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("published_by", uid, sa.ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rolled_back_by", uid, sa.ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("rolled_back_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rollback_reason", sa.Text(), nullable=True),
        sa.CheckConstraint("status in ('published','rolled_back')", name="content_release_status"),
    )
    op.create_table(
        "content_release_entry",
        sa.Column("id", uid, primary_key=True),
        sa.Column("release_id", uid, sa.ForeignKey("content_release.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("item_id", uid, sa.ForeignKey("content_item.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version_id", uid, sa.ForeignKey("content_version.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("previous_version_id", uid, sa.ForeignKey("content_version.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.UniqueConstraint("release_id", "item_id", name="uq_content_release_entry_item"),
    )
    op.create_index("ix_content_release_entry_release_id", "content_release_entry", ["release_id"])
    op.create_index("ix_content_release_entry_item_id", "content_release_entry", ["item_id"])


def downgrade() -> None:
    op.drop_index("ix_content_release_entry_item_id", table_name="content_release_entry")
    op.drop_index("ix_content_release_entry_release_id", table_name="content_release_entry")
    op.drop_table("content_release_entry")
    op.drop_table("content_release")
