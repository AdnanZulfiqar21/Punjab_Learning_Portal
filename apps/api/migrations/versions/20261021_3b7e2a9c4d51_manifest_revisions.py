"""Answer-mapping revision history (W03.S2.T2, REGION-MAP-01).

One row per saved mapping. The table is new and only added to, so the previous build, which doesn't read it, keeps
working; existing attempts have no history before this release.

Revision ID: 3b7e2a9c4d51
Revises: f8a21c6d4e90
Create Date: 2026-10-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "3b7e2a9c4d51"
down_revision = "f8a21c6d4e90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "written_manifest_revision",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "attempt_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("written_attempt.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("manifest", postgresql.JSONB(), nullable=False),
        sa.Column("saved_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("attempt_id", "revision", name="uq_written_manifest_revision"),
    )
    op.create_index("ix_written_manifest_revision_attempt_id", "written_manifest_revision", ["attempt_id"])


def downgrade() -> None:
    op.drop_index("ix_written_manifest_revision_attempt_id", table_name="written_manifest_revision")
    op.drop_table("written_manifest_revision")
