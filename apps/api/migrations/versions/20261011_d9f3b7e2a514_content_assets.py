"""content_asset, content_asset_version: owned master archive for content assets (P07.S2.T4, ASSETS-01)

Revision ID: d9f3b7e2a514
Revises: c8e4a1f7d263
Create Date: 2026-10-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d9f3b7e2a514"
down_revision = "c8e4a1f7d263"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_asset",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("grade_number", sa.SmallInteger(), nullable=False),
        sa.Column("subject_code", sa.String(length=40), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind in ('image','handout','caption','diagram_source')", name="content_asset_kind"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "content_asset_version",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("asset_id", sa.UUID(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("master_key", sa.Text(), nullable=False),
        sa.Column("master_sha256", sa.String(length=64), nullable=False),
        sa.Column("master_bytes", sa.Integer(), nullable=False),
        sa.Column("media_type", sa.String(length=60), nullable=False),
        sa.Column("delivery_key", sa.Text(), nullable=True),
        sa.Column("delivery_sha256", sa.String(length=64), nullable=True),
        sa.Column("delivery_media_type", sa.String(length=60), nullable=True),
        sa.Column("delivery_state", sa.String(length=8), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("pages", sa.Integer(), nullable=True),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("delivery_state in ('ready','none','purged')", name="content_asset_version_delivery"),
        sa.ForeignKeyConstraint(["asset_id"], ["content_asset.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id", "number", name="uq_content_asset_version_number"),
    )
    op.create_index("ix_content_asset_version_asset_id", "content_asset_version", ["asset_id"])


def downgrade() -> None:
    op.drop_index("ix_content_asset_version_asset_id", table_name="content_asset_version")
    op.drop_table("content_asset_version")
    op.drop_table("content_asset")
