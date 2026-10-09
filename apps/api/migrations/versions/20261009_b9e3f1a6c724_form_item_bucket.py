"""form_item.grade_number / subject_code (OCT9-03: progress buckets from each frozen question)

Revision ID: b9e3f1a6c724
Revises: a7d4e2c9f163
Create Date: 2026-10-09

Existing rows are backfilled from their content item (class and subject are fixed for an item).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b9e3f1a6c724"
down_revision = "a7d4e2c9f163"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("form_item", sa.Column("grade_number", sa.SmallInteger(), nullable=True))
    op.add_column("form_item", sa.Column("subject_code", sa.String(length=40), nullable=True))
    op.execute(
        "update form_item fi set grade_number = ci.grade_number, subject_code = ci.subject_code "
        "from content_item ci where ci.id = fi.item_id"
    )
    op.alter_column("form_item", "grade_number", nullable=False)
    op.alter_column("form_item", "subject_code", nullable=False)


def downgrade() -> None:
    op.drop_column("form_item", "subject_code")
    op.drop_column("form_item", "grade_number")
