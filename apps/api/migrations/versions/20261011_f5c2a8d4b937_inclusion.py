"""inclusion_record: concept inclusion per mapping and year (P05.S2, INCLUSION-01)

Revision ID: f5c2a8d4b937
Revises: e3b9f1c7a426
Create Date: 2026-10-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f5c2a8d4b937"
down_revision = "e3b9f1c7a426"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inclusion_record",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("concept_id", sa.UUID(), nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("year", sa.SmallInteger(), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_version", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("published_by", sa.UUID(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("scope in ('full_curriculum', 'board_syllabus', 'mdcat', 'ecat')", name="inclusion_scope"),
        sa.CheckConstraint("state in ('included', 'excluded', 'not_applicable', 'unverified')", name="inclusion_state"),
        sa.CheckConstraint("status in ('draft', 'published')", name="inclusion_status"),
        sa.ForeignKeyConstraint(["concept_id"], ["concept.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["published_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_inclusion_record_concept_id"), "inclusion_record", ["concept_id"], unique=False)
    op.create_index(
        "uq_inclusion_concept_scope_year",
        "inclusion_record",
        ["concept_id", "scope", sa.literal_column("coalesce(year, 0)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_inclusion_concept_scope_year", table_name="inclusion_record")
    op.drop_index(op.f("ix_inclusion_record_concept_id"), table_name="inclusion_record")
    op.drop_table("inclusion_record")
