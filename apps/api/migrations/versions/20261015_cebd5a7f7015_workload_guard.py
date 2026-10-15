"""health_sample and workload_guard: the written workload guard (W09.S1.T3, WORKLOAD-GUARD-01)

Two new tables. API processes write samples and any process may write the guard row; the previous build neither reads
nor writes them, so it keeps running written work unguarded during a rolling deployment.

Revision ID: cebd5a7f7015
Revises: a7e159815370
Create Date: 2026-10-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "cebd5a7f7015"
down_revision = "a7e159815370"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "health_sample",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("process", sa.String(120), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_s", sa.Float(), nullable=False),
        sa.Column("saves", sa.Integer(), nullable=False),
        sa.Column("slow_saves", sa.Integer(), nullable=False),
        sa.Column("save_errors", sa.Integer(), nullable=False),
        sa.Column("pool_in_use", sa.Integer(), nullable=False),
        sa.Column("pool_size", sa.Integer(), nullable=False),
    )
    op.create_index("ix_health_sample_window_end", "health_sample", ["window_end"])
    op.create_table(
        "workload_guard",
        sa.Column("name", sa.String(20), primary_key=True),
        sa.Column("state", sa.String(10), nullable=False),
        sa.Column("ramp", sa.Integer(), nullable=False),
        sa.Column("faults", postgresql.JSONB(), nullable=False),
        sa.Column("unhealthy_checks", sa.Integer(), nullable=False),
        sa.Column("healthy_checks", sa.Integer(), nullable=False),
        sa.Column("last_fault_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.CheckConstraint("state in ('healthy','paused','recovering')", name="workload_guard_state"),
    )


def downgrade() -> None:
    op.drop_table("workload_guard")
    op.drop_index("ix_health_sample_window_end", table_name="health_sample")
    op.drop_table("health_sample")
