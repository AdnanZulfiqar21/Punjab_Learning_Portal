"""versioned exam profiles (P05.S3, EXAMPROFILE-01)

Revision ID: b6d2e8f4a137
Revises: a1e5c9f3b708
Create Date: 2026-10-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b6d2e8f4a137"
down_revision = "a1e5c9f3b708"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exam_profile",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("eligibility_note", sa.Text(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "exam_profile_version",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("profile_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("verifications", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("published_by", sa.UUID(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status in ('draft', 'verified', 'published', 'retired')", name="exam_profile_status"),
        sa.ForeignKeyConstraint(["profile_id"], ["exam_profile.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["published_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "version", name="uq_exam_profile_version"),
    )
    op.create_index(op.f("ix_exam_profile_version_profile_id"), "exam_profile_version", ["profile_id"], unique=False)
    op.create_index(
        "uq_exam_profile_published",
        "exam_profile_version",
        ["profile_id"],
        unique=True,
        postgresql_where=sa.text("status = 'published'"),
    )


def downgrade() -> None:
    op.drop_index("uq_exam_profile_published", table_name="exam_profile_version")
    op.drop_index(op.f("ix_exam_profile_version_profile_id"), table_name="exam_profile_version")
    op.drop_table("exam_profile_version")
    op.drop_table("exam_profile")
