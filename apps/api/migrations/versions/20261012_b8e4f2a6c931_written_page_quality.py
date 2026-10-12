"""written_page.quality: quality-check warnings per uploaded page (W03.S2.T1, SCAN-QUALITY-01)

Revision ID: b8e4f2a6c931
Revises: a7d3e9f1c258
Create Date: 2026-10-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b8e4f2a6c931"
down_revision = "a7d3e9f1c258"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "written_page",
        sa.Column(
            "quality",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("written_page", "quality")
