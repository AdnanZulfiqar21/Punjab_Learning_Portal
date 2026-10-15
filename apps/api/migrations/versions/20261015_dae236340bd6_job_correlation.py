"""correlation_id on job rows: content_import_batch, export_job, notification_delivery, written_regrade_job (P03.S4.T2,
CORRELATION-01)

Four nullable columns. The previous build neither reads nor writes them; rows created before them stay null.

Revision ID: dae236340bd6
Revises: 5d7c1e7a1030
Create Date: 2026-10-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "dae236340bd6"
down_revision = "5d7c1e7a1030"
branch_labels = None
depends_on = None

TABLES = ("content_import_batch", "export_job", "notification_delivery", "written_regrade_job")


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("correlation_id", sa.String(64), nullable=True))


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, "correlation_id")
