"""source reviews and syllabus notices (P16.S3.T3, ACADEMIC-UPDATES-01)

Revision ID: a1e5c9f3b708
Revises: e8c1b7d4a206
Create Date: 2026-10-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a1e5c9f3b708"
down_revision = "e8c1b7d4a206"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_review",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_document_id", sa.UUID(), nullable=False),
        sa.Column("reviewed_by", sa.UUID(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_document.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_source_review_source_document_id"), "source_review", ["source_document_id"], unique=False)
    op.create_table(
        "syllabus_notice",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("grade_number", sa.SmallInteger(), nullable=False),
        sa.Column("subject_code", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("logged_by", sa.UUID(), nullable=False),
        sa.Column("logged_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("decision", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status in ('open','accepted','dismissed')", name="syllabus_notice_status"),
        sa.CheckConstraint("grade_number in (11, 12)", name="syllabus_notice_grade"),
        sa.ForeignKeyConstraint(["logged_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["decided_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("syllabus_notice")
    op.drop_index(op.f("ix_source_review_source_document_id"), table_name="source_review")
    op.drop_table("source_review")
