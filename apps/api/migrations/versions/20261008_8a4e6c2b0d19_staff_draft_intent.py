"""staff draft intent (PR32-02)

Revision ID: 8a4e6c2b0d19
Revises: 5c2d9e7f1a3b
Create Date: 2026-10-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "8a4e6c2b0d19"
down_revision = "5c2d9e7f1a3b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "written_score_version", sa.Column("draft_intent", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("written_score_version", "draft_intent")
