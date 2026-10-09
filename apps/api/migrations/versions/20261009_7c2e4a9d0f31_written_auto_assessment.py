"""automatic written assessment stage records (W05, AUTOASSESS-01)

Revision ID: 7c2e4a9d0f31
Revises: 0a7d3e9f1b52
Create Date: 2026-10-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "7c2e4a9d0f31"
down_revision = "0a7d3e9f1b52"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "written_auto_assessment",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("attempt_id", sa.UUID(), nullable=False),
        sa.Column("receipt_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("rubric_version_id", sa.UUID(), nullable=False),
        sa.Column("assessor", sa.String(length=40), nullable=False),
        sa.Column("evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("proposal", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("flags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["written_attempt.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["receipt_id"], ["written_receipt.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["rubric_version_id"], ["content_version.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "receipt_id", "position", "rubric_version_id", "assessor", name="uq_written_auto_assessment_unit"
        ),
    )
    op.create_index(
        op.f("ix_written_auto_assessment_attempt_id"), "written_auto_assessment", ["attempt_id"], unique=False
    )
    op.create_index(op.f("ix_written_auto_assessment_status"), "written_auto_assessment", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_written_auto_assessment_status"), table_name="written_auto_assessment")
    op.drop_index(op.f("ix_written_auto_assessment_attempt_id"), table_name="written_auto_assessment")
    op.drop_table("written_auto_assessment")
