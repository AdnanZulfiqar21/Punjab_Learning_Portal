"""written_attempt.end_reason: why an unsealed written attempt ended (W08.S1.T3, PERMITS-01)

Nullable: earlier rows (and the previous build) leave it empty, which means the upload window closed.

Revision ID: f3c8d6e0a579
Revises: e2b7c5d9f468
Create Date: 2026-10-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f3c8d6e0a579"
down_revision = "e2b7c5d9f468"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("written_attempt", sa.Column("end_reason", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("written_attempt", "end_reason")
