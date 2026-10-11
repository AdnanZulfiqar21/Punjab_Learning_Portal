"""attempt.flagged: questions a learner flagged to come back to (P11.S3.T2, FLAGS-01)

Revision ID: a7c3e9d1f264
Revises: f3b8d2a6c947
Create Date: 2026-10-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a7c3e9d1f264"
down_revision = "f3b8d2a6c947"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "attempt",
        sa.Column(
            "flagged", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("attempt", "flagged")
