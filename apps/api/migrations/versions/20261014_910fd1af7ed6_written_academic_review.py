"""written_academic_review: methods a marking guide doesn't cover go to academic review (ACADEMIC-REVIEW-01)

A new table only; nothing existing changes, so the previous build is unaffected (it never reads or writes it).

Revision ID: 910fd1af7ed6
Revises: a4d9e7f1b680
Create Date: 2026-10-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "910fd1af7ed6"
down_revision = "a4d9e7f1b680"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "written_academic_review",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("attempt_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.Column("rubric_version_id", sa.UUID(), nullable=True),
        sa.Column("grade_number", sa.SmallInteger(), nullable=False),
        sa.Column("subject_code", sa.String(length=40), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("raised_by", sa.UUID(), nullable=False),
        sa.Column("raised_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("resolution", sa.String(length=20), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("adjudication_id", sa.UUID(), nullable=True),
        sa.Column("resolved_by", sa.UUID(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind in ('unlisted_method','rubric_defect')", name="written_academic_review_kind"),
        sa.CheckConstraint("status in ('open','resolved')", name="written_academic_review_status"),
        sa.CheckConstraint(
            "resolution is null or resolution in ('guide_corrected','not_covered')",
            name="written_academic_review_resolution",
        ),
        sa.ForeignKeyConstraint(["attempt_id"], ["written_attempt.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["case_id"], ["written_review_case.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["rubric_version_id"], ["content_version.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["adjudication_id"], ["written_rubric_adjudication.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["raised_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["resolved_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_written_academic_review_attempt_id"), "written_academic_review", ["attempt_id"], unique=False
    )
    op.create_index(
        "uq_written_academic_review_open",
        "written_academic_review",
        ["attempt_id", "position"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )


def downgrade() -> None:
    op.drop_index("uq_written_academic_review_open", table_name="written_academic_review")
    op.drop_index(op.f("ix_written_academic_review_attempt_id"), table_name="written_academic_review")
    op.drop_table("written_academic_review")
