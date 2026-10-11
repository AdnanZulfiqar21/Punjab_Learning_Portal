"""lecture.markers: chapter markers timed against the master video (P07.S3.T2, MARKERS-01)

Revision ID: d7a2c5e9f318
Revises: b6d1e4a8c205
Create Date: 2026-10-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d7a2c5e9f318"
down_revision = "b6d1e4a8c205"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("lecture", sa.Column("markers", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("lecture", "markers")
