"""media_upload: resumable master-video upload sessions (P07.S2.T1, MEDIA-UPLOAD-01)

Revision ID: b6d1e4a8c205
Revises: c4e8b2f6a913
Create Date: 2026-10-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b6d1e4a8c205"
down_revision = "c4e8b2f6a913"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "media_upload",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("lecture_id", sa.UUID(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=40), nullable=False),
        sa.Column("bytes", sa.BigInteger(), nullable=False),
        sa.Column("duration_s", sa.Integer(), nullable=False),
        sa.Column("expected_sha256", sa.String(length=64), nullable=True),
        sa.Column("received", sa.BigInteger(), nullable=False),
        sa.Column("state", sa.String(length=12), nullable=False),
        sa.Column("failure", sa.Text(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("state in ('uploading', 'processing', 'ready', 'failed')", name="media_upload_state"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["lecture_id"], ["lecture.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_media_upload_lecture_id"), "media_upload", ["lecture_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_media_upload_lecture_id"), table_name="media_upload")
    op.drop_table("media_upload")
