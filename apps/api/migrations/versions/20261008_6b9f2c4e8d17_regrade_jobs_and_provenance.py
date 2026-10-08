"""regrade jobs, score provenance and multi-supersede (PR #34 review W06-03..W06-07)

Revision ID: 6b9f2c4e8d17
Revises: 3e7b1d9c5a42
Create Date: 2026-10-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "6b9f2c4e8d17"
down_revision = "3e7b1d9c5a42"
branch_labels = None
depends_on = None

J = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    # Corrections may replace several active corrections at once, and name their successor.
    op.add_column("written_rubric_adjudication", sa.Column("supersedes_ids", J, server_default="[]", nullable=False))
    op.add_column("written_rubric_adjudication", sa.Column("superseded_by_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_adjudication_superseded_by",
        "written_rubric_adjudication",
        "written_rubric_adjudication",
        ["superseded_by_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute(
        "update written_rubric_adjudication set supersedes_ids = jsonb_build_array(supersedes_id::text) "
        "where supersedes_id is not null"
    )
    op.execute(
        "update written_rubric_adjudication o set superseded_by_id = n.id from written_rubric_adjudication n "
        "where n.supersedes_id = o.id"
    )
    op.drop_column("written_rubric_adjudication", "supersedes_id")

    # Regrade checkpoints: failures are recorded, never reported as done.
    op.drop_constraint("written_regrade_status", "written_rubric_regrade", type_="check")
    op.execute("update written_rubric_regrade set status = 'failed' where status = 'deferred'")
    op.create_check_constraint("written_regrade_status", "written_rubric_regrade", "status in ('done','failed')")
    op.add_column("written_rubric_regrade", sa.Column("job_id", sa.UUID(), nullable=True))
    op.add_column("written_rubric_regrade", sa.Column("error", sa.Text(), nullable=True))

    op.create_table(
        "written_regrade_job",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "adjudication_id",
            sa.UUID(),
            sa.ForeignKey("written_rubric_adjudication.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("requested_by", sa.UUID(), sa.ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("processed", sa.Integer(), nullable=False),
        sa.Column("regraded", sa.Integer(), nullable=False),
        sa.Column("unaffected", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("remaining", sa.Integer(), nullable=True),
        sa.Column("batches", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("lease_owner", sa.String(120), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status in ('queued','running','succeeded','failed','superseded')", name="written_regrade_job_status"
        ),
    )
    op.create_index("ix_written_regrade_job_adjudication_id", "written_regrade_job", ["adjudication_id"])
    op.create_index(
        "uq_written_regrade_job_open",
        "written_regrade_job",
        ["adjudication_id"],
        unique=True,
        postgresql_where=sa.text("status in ('queued','running')"),
    )

    # Immutable correction provenance on every score version from now on (null = released before it was recorded).
    op.add_column("written_score_version", sa.Column("effective_adjudication", J, nullable=True))
    op.add_column("written_score_version", sa.Column("adjudication_hash", sa.String(64), nullable=True))
    op.create_index(
        "uq_written_regrade_version",
        "written_score_version",
        ["attempt_id", "adjudication_hash"],
        unique=True,
        postgresql_where=sa.text("case_kind = 'regrade' and decision_method = 'SYSTEM'"),
    )


def downgrade() -> None:
    op.drop_index("uq_written_regrade_version", table_name="written_score_version")
    op.drop_column("written_score_version", "adjudication_hash")
    op.drop_column("written_score_version", "effective_adjudication")
    op.drop_index("uq_written_regrade_job_open", table_name="written_regrade_job")
    op.drop_index("ix_written_regrade_job_adjudication_id", table_name="written_regrade_job")
    op.drop_table("written_regrade_job")
    op.drop_column("written_rubric_regrade", "error")
    op.drop_column("written_rubric_regrade", "job_id")
    op.drop_constraint("written_regrade_status", "written_rubric_regrade", type_="check")
    op.execute("update written_rubric_regrade set status = 'deferred' where status = 'failed'")
    op.create_check_constraint("written_regrade_status", "written_rubric_regrade", "status in ('done','deferred')")
    op.add_column(
        "written_rubric_adjudication",
        sa.Column(
            "supersedes_id",
            sa.UUID(),
            sa.ForeignKey("written_rubric_adjudication.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.execute(
        "update written_rubric_adjudication set supersedes_id = (supersedes_ids->>0)::uuid "
        "where jsonb_array_length(supersedes_ids) > 0"
    )
    op.drop_constraint("fk_adjudication_superseded_by", "written_rubric_adjudication", type_="foreignkey")
    op.drop_column("written_rubric_adjudication", "superseded_by_id")
    op.drop_column("written_rubric_adjudication", "supersedes_ids")
