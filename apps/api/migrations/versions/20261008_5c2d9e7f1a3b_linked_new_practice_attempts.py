"""linked new practice attempts (W04.S3.T3)

Revision ID: 5c2d9e7f1a3b
Revises: 74ef206e3de6
Create Date: 2026-10-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "5c2d9e7f1a3b"
down_revision = "74ef206e3de6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("written_form", sa.Column("linked_from_attempt_id", sa.UUID(), nullable=True))
    op.add_column("written_form", sa.Column("link_reason", sa.String(length=14), nullable=True))
    op.add_column("written_form", sa.Column("link_revision_id", sa.UUID(), nullable=True))
    op.add_column("written_form", sa.Column("link_positions", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_foreign_key(
        "fk_written_form_linked_from",
        "written_form",
        "written_attempt",
        ["linked_from_attempt_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_written_form_linked_from_attempt_id", "written_form", ["linked_from_attempt_id"])
    op.create_check_constraint(
        "written_form_link",
        "written_form",
        "(linked_from_attempt_id is null) = (link_reason is null) and "
        "(link_reason is null or link_reason in ('NEW_CONTENT','INDETERMINATE','REWRITE'))",
    )


def downgrade() -> None:
    op.drop_constraint("written_form_link", "written_form", type_="check")
    op.drop_index("ix_written_form_linked_from_attempt_id", table_name="written_form")
    op.drop_constraint("fk_written_form_linked_from", "written_form", type_="foreignkey")
    for col in ("link_positions", "link_revision_id", "link_reason", "linked_from_attempt_id"):
        op.drop_column("written_form", col)
