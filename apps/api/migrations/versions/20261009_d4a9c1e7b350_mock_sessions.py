"""scheduled mock sessions and accommodations (P09.S2.T3, SCHEDULE-01)

Revision ID: d4a9c1e7b350
Revises: c8f1a3d5e902
Create Date: 2026-10-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d4a9c1e7b350"
down_revision = "c8f1a3d5e902"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mock_session",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("profile_version_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("timezone", sa.String(length=60), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_closes_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_closes_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("results_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("late_entry", sa.String(length=14), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("late_entry in ('fixed_end','full_duration')", name="mock_session_late_entry"),
        sa.CheckConstraint("status in ('scheduled','cancelled')", name="mock_session_status"),
        sa.CheckConstraint(
            "entry_closes_at > starts_at and window_closes_at >= entry_closes_at", name="mock_session_window"
        ),
        sa.ForeignKeyConstraint(["profile_version_id"], ["exam_profile_version.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "mock_accommodation",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("extra_minutes", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("granted_by", sa.UUID(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["mock_session.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["granted_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "user_id", name="uq_mock_accommodation"),
    )
    op.create_index(op.f("ix_mock_accommodation_session_id"), "mock_accommodation", ["session_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_mock_accommodation_session_id"), table_name="mock_accommodation")
    op.drop_table("mock_accommodation")
    op.drop_table("mock_session")
