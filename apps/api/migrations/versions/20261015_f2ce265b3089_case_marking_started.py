"""written_review_case.marking_started_at: when the current teacher took the case (W06.S3.T1, MARKING-TIME-01)

One nullable column. The previous build neither reads nor writes it.

Revision ID: f2ce265b3089
Revises: 1311c92533d7
Create Date: 2026-10-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f2ce265b3089"
down_revision = "1311c92533d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("written_review_case", sa.Column("marking_started_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("written_review_case", "marking_started_at")
