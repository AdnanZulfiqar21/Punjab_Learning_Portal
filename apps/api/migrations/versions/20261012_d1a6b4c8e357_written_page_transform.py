"""written_page.transform: the learner's turn, trim and readability choices for a page (W03.S1.T3, TRANSFORMS-01)

Revision ID: d1a6b4c8e357
Revises: c9f5a3b7d042
Create Date: 2026-10-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d1a6b4c8e357"
down_revision = "c9f5a3b7d042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "written_page",
        sa.Column(
            "transform",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("written_page", "transform")
