"""correction-chain policy: retained descendants and chain-applied regrade rows (PR #36 review NEW-14/NEW-15)

Revision ID: 9d1c3a7e5b20
Revises: 6b9f2c4e8d17
Create Date: 2026-10-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "9d1c3a7e5b20"
down_revision = "6b9f2c4e8d17"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "written_rubric_adjudication",
        sa.Column(
            "retained_descendant_ids", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False
        ),
    )
    op.add_column("written_rubric_regrade", sa.Column("applied_via", sa.UUID(), nullable=True))


def downgrade() -> None:
    op.drop_column("written_rubric_regrade", "applied_via")
    op.drop_column("written_rubric_adjudication", "retained_descendant_ids")
