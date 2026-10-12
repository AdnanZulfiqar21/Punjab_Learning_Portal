"""written_calibration: blinded teacher marks compared with automatic proposals (W06.S1.T3, CALIBRATION-01)

Revision ID: e2b7c5d9f468
Revises: d1a6b4c8e357
Create Date: 2026-10-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e2b7c5d9f468"
down_revision = "d1a6b4c8e357"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "written_calibration",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("attempt_id", sa.UUID(), nullable=False),
        sa.Column("grade_number", sa.SmallInteger(), nullable=False),
        sa.Column("subject_code", sa.String(length=40), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("score_version_id", sa.UUID(), nullable=False),
        sa.Column("auto_assessment_id", sa.UUID(), nullable=False),
        sa.Column("teacher_units", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("proposal_units", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("disagreements", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("verdicts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("adjudicated_by", sa.UUID(), nullable=True),
        sa.Column("adjudicated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status in ('agreed','open','adjudicated')", name="written_calibration_status"),
        sa.ForeignKeyConstraint(["adjudicated_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["attempt_id"], ["written_attempt.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["auto_assessment_id"], ["written_auto_assessment.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["score_version_id"], ["written_score_version.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("score_version_id", "auto_assessment_id", name="uq_written_calibration_pair"),
    )
    op.create_index("ix_written_calibration_attempt_id", "written_calibration", ["attempt_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_written_calibration_attempt_id", table_name="written_calibration")
    op.drop_table("written_calibration")
