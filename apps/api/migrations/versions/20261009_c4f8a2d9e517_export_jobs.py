"""export_job (P16.S4.T2, EXPORTS-01: asynchronous reporting exports)

Revision ID: c4f8a2d9e517
Revises: b9e3f1a6c724
Create Date: 2026-10-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c4f8a2d9e517"
down_revision = "b9e3f1a6c724"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "export_job",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("tries", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("file_key", sa.String(length=120), nullable=True),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("downloads", sa.Integer(), nullable=False),
        sa.Column("lease_owner", sa.String(length=120), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status in ('queued','running','ready','failed','cancelled','expired')", name="export_job_status"
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_export_job_queue", "export_job", ["status", "created_at"], unique=False)
    op.create_index(op.f("ix_export_job_owner_id"), "export_job", ["owner_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_export_job_owner_id"), table_name="export_job")
    op.drop_index("ix_export_job_queue", table_name="export_job")
    op.drop_table("export_job")
