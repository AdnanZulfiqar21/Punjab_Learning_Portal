"""question pools: practice or mock-only (P08.S3.T3, MOCKPOOL-01)

Revision ID: c8f1a3d5e902
Revises: b6d2e8f4a137
Create Date: 2026-10-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c8f1a3d5e902"
down_revision = "b6d2e8f4a137"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "content_item",
        sa.Column("question_pool", sa.String(length=10), server_default="practice", nullable=False),
    )
    op.create_check_constraint("content_item_question_pool", "content_item", "question_pool in ('practice','mock')")


def downgrade() -> None:
    op.drop_constraint("content_item_question_pool", "content_item", type_="check")
    op.drop_column("content_item", "question_pool")
