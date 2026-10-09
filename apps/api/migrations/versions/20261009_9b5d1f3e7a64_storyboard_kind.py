"""storyboard content kind (P07.S4, STORYBOARD-01)

Revision ID: 9b5d1f3e7a64
Revises: 7c2e4a9d0f31
Create Date: 2026-10-09
"""

from __future__ import annotations

from alembic import op

revision = "9b5d1f3e7a64"
down_revision = "7c2e4a9d0f31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("content_item_kind", "content_item", type_="check")
    op.create_check_constraint(
        "content_item_kind", "content_item", "kind in ('lesson', 'mcq', 'written', 'rubric', 'storyboard')"
    )


def downgrade() -> None:
    op.drop_constraint("content_item_kind", "content_item", type_="check")
    op.create_check_constraint("content_item_kind", "content_item", "kind in ('lesson', 'mcq', 'written', 'rubric')")
