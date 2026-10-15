"""comparison_snapshot and comparison_member: honest learner comparisons for fixed forms (P12.S2.T3, COMPARISON-01)

Two new tables, written only by `portal-comparison-snapshots` and read by the result endpoint. The previous build
neither reads nor writes them.

Revision ID: b780d235c059
Revises: a7e159815370
Create Date: 2026-10-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b780d235c059"
down_revision = "a7e159815370"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "comparison_snapshot",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("mock_session.id", ondelete="RESTRICT", name="fk_comparison_snapshot_session"),
            nullable=False,
        ),
        sa.Column("timing_group", sa.String(12), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(10), nullable=False),
        sa.Column("learners", sa.Integer(), nullable=False),
        sa.Column("maximum", sa.Integer(), nullable=True),
        sa.Column("scoring_policy_version", sa.SmallInteger(), nullable=False),
        sa.Column("adjudication_hash", sa.String(64), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("inputs_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("session_id", "timing_group", "version", name="uq_comparison_snapshot_version"),
        sa.CheckConstraint("state in ('published','too_few','pending')", name="comparison_snapshot_state"),
        sa.CheckConstraint("timing_group in ('standard','accommodated')", name="comparison_snapshot_timing_group"),
    )
    op.create_index("ix_comparison_snapshot_session_id", "comparison_snapshot", ["session_id"])
    op.create_table(
        "comparison_member",
        sa.Column(
            "snapshot_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("comparison_snapshot.id", ondelete="RESTRICT", name="fk_comparison_member_snapshot"),
            primary_key=True,
        ),
        sa.Column(
            "attempt_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("attempt.id", ondelete="RESTRICT", name="fk_comparison_member_attempt"),
            primary_key=True,
        ),
        sa.Column(
            "score_version_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("score_version.id", ondelete="RESTRICT", name="fk_comparison_member_score_version"),
            nullable=False,
        ),
        sa.Column("raw", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("comparison_member")
    op.drop_index("ix_comparison_snapshot_session_id", table_name="comparison_snapshot")
    op.drop_table("comparison_snapshot")
