"""passage content kind; form_item.passage_version_id pins a question's passage (P08.S1.T1, PASSAGES-01)

Revision ID: f3b8d2a6c947
Revises: e2a7c4f9b831
Create Date: 2026-10-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f3b8d2a6c947"
down_revision = "e2a7c4f9b831"
branch_labels = None
depends_on = None

KINDS_BEFORE = "kind in ('lesson', 'mcq', 'written', 'rubric', 'storyboard')"
KINDS_AFTER = "kind in ('lesson', 'mcq', 'written', 'rubric', 'storyboard', 'passage')"


def upgrade() -> None:
    op.drop_constraint("content_item_kind", "content_item", type_="check")
    op.create_check_constraint("content_item_kind", "content_item", KINDS_AFTER)
    op.add_column("form_item", sa.Column("passage_version_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "form_item_passage_version_id_fkey",
        "form_item",
        "content_version",
        ["passage_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("form_item_passage_version_id_fkey", "form_item", type_="foreignkey")
    op.drop_column("form_item", "passage_version_id")
    op.drop_constraint("content_item_kind", "content_item", type_="check")
    op.create_check_constraint("content_item_kind", "content_item", KINDS_BEFORE)
