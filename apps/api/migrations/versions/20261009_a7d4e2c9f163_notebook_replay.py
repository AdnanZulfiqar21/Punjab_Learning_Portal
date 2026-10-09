"""attempt.notebook_applied_at (OCT9-01/OCT9-02: notebook derived by replay; held results applied on release)

Revision ID: a7d4e2c9f163
Revises: f6c1e3a9d572
Create Date: 2026-10-09

Existing finalised attempts were already reflected in the notebook when they were submitted, so they are marked
applied at their finalisation time.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a7d4e2c9f163"
down_revision = "f6c1e3a9d572"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("attempt", sa.Column("notebook_applied_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("update attempt set notebook_applied_at = finalised_at where status = 'finalised'")


def downgrade() -> None:
    op.drop_column("attempt", "notebook_applied_at")
