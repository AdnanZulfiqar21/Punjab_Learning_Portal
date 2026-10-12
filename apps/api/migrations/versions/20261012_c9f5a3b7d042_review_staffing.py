"""written_review_capacity staffing: productive hours, fixed obligations, minutes per script, turnaround (W06.S3.T2,
STAFFING-01)

Nullable columns only: the previous build keeps writing capacity rows unchanged (MIGRATION-COMPAT-01). The API sets the
four together and checks them.

Revision ID: c9f5a3b7d042
Revises: b8e4f2a6c931
Create Date: 2026-10-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c9f5a3b7d042"
down_revision = "b8e4f2a6c931"
branch_labels = None
depends_on = None

COLUMNS = ("reviewer_hours_per_week", "fixed_hours_per_week", "minutes_per_script", "turnaround_days")


def upgrade() -> None:
    for name in COLUMNS:
        op.add_column("written_review_capacity", sa.Column(name, sa.Integer(), nullable=True))


def downgrade() -> None:
    for name in reversed(COLUMNS):
        op.drop_column("written_review_capacity", name)
