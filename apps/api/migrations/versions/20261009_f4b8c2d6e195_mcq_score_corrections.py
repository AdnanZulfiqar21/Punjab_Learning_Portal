"""MCQ score corrections (§5.7, P10.S3.T4)

Revision ID: f4b8c2d6e195
Revises: e2a9b4c7d613
Create Date: 2026-10-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f4b8c2d6e195"
down_revision = "e2a9b4c7d613"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mcq_adjudication",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("version_id", sa.UUID(), nullable=False),
        sa.Column("defect", sa.String(length=10), nullable=False),
        sa.Column("corrected_option_id", sa.String(length=80), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("decided_by", sa.UUID(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("supersedes_id", sa.UUID(), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("defect in ('VOID','KEY_ERROR')", name="mcq_adjudication_defect"),
        sa.CheckConstraint("status in ('effective','superseded')", name="mcq_adjudication_status"),
        sa.CheckConstraint(
            "(defect = 'KEY_ERROR') = (corrected_option_id is not null)", name="mcq_adjudication_corrected_key"
        ),
        sa.ForeignKeyConstraint(["item_id"], ["content_item.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["version_id"], ["content_version.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["decided_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["mcq_adjudication.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mcq_adjudication_item_id"), "mcq_adjudication", ["item_id"], unique=False)
    op.create_index(op.f("ix_mcq_adjudication_version_id"), "mcq_adjudication", ["version_id"], unique=False)
    op.create_index(
        "uq_mcq_adjudication_effective",
        "mcq_adjudication",
        ["version_id"],
        unique=True,
        postgresql_where=sa.text("status = 'effective'"),
    )


def downgrade() -> None:
    op.drop_index("uq_mcq_adjudication_effective", table_name="mcq_adjudication")
    op.drop_index(op.f("ix_mcq_adjudication_version_id"), table_name="mcq_adjudication")
    op.drop_index(op.f("ix_mcq_adjudication_item_id"), table_name="mcq_adjudication")
    op.drop_table("mcq_adjudication")
