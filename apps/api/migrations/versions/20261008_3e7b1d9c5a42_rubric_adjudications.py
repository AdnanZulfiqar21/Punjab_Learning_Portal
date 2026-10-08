"""rubric adjudications across attempts (W06.S2.T3)

Revision ID: 3e7b1d9c5a42
Revises: 8a4e6c2b0d19
Create Date: 2026-10-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "3e7b1d9c5a42"
down_revision = "8a4e6c2b0d19"
branch_labels = None
depends_on = None

J = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "written_rubric_adjudication",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("rubric_item_id", sa.UUID(), sa.ForeignKey("content_item.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("grade_number", sa.SmallInteger(), nullable=False),
        sa.Column("subject_code", sa.String(40), nullable=False),
        sa.Column("from_version_ids", J, nullable=False),
        sa.Column("to_version_id", sa.UUID(), sa.ForeignKey("content_version.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("compatibility", J, nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("supersedes_id", sa.UUID(), sa.ForeignKey("written_rubric_adjudication.id", ondelete="RESTRICT")),
        sa.Column("approved_by", sa.UUID(), sa.ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status in ('active','superseded')", name="written_adjudication_status"),
    )
    op.create_index("ix_written_rubric_adjudication_rubric_item_id", "written_rubric_adjudication", ["rubric_item_id"])
    op.create_table(
        "written_rubric_target",
        sa.Column("attempt_id", sa.UUID(), sa.ForeignKey("written_attempt.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("position", sa.SmallInteger(), primary_key=True),
        sa.Column(
            "rubric_version_id", sa.UUID(), sa.ForeignKey("content_version.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("adjudication_ids", J, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "written_notice",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("attempt_id", sa.UUID(), sa.ForeignKey("written_attempt.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("cause_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("positions", J, nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind in ('rubric_correction')", name="written_notice_kind"),
    )
    op.create_index("ix_written_notice_attempt_id", "written_notice", ["attempt_id"])
    op.create_index("uq_written_notice", "written_notice", ["attempt_id", "cause_id", "kind"], unique=True)
    op.add_column("written_review_case", sa.Column("adjudication_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_case_adjudication",
        "written_review_case",
        "written_rubric_adjudication",
        ["adjudication_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint("written_case_kind", "written_review_case", type_="check")
    op.create_check_constraint(
        "written_case_kind", "written_review_case", "case_kind in ('initial','recheck','completion','regrade')"
    )
    op.add_column("written_score_version", sa.Column("regrade_detail", J, nullable=True))
    op.create_table(
        "written_rubric_regrade",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "adjudication_id",
            sa.UUID(),
            sa.ForeignKey("written_rubric_adjudication.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("attempt_id", sa.UUID(), sa.ForeignKey("written_attempt.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("outcomes", J, nullable=False),
        sa.Column("score_version_id", sa.UUID(), sa.ForeignKey("written_score_version.id", ondelete="RESTRICT")),
        sa.Column("case_id", sa.UUID(), sa.ForeignKey("written_review_case.id", ondelete="RESTRICT")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("adjudication_id", "attempt_id", name="uq_written_regrade"),
        sa.CheckConstraint("status in ('done','deferred')", name="written_regrade_status"),
    )
    op.create_index("ix_written_rubric_regrade_adjudication_id", "written_rubric_regrade", ["adjudication_id"])


def downgrade() -> None:
    op.drop_table("written_rubric_regrade")
    op.drop_column("written_score_version", "regrade_detail")
    op.drop_constraint("written_case_kind", "written_review_case", type_="check")
    op.create_check_constraint(
        "written_case_kind", "written_review_case", "case_kind in ('initial','recheck','completion')"
    )
    op.drop_constraint("fk_case_adjudication", "written_review_case", type_="foreignkey")
    op.drop_column("written_review_case", "adjudication_id")
    op.drop_table("written_notice")
    op.drop_table("written_rubric_target")
    op.drop_table("written_rubric_adjudication")
