"""structured content import batches (P06.S2, IMPORT-01)

Revision ID: 0a7d3e9f1b52
Revises: f4b8c2d6e195
Create Date: 2026-10-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0a7d3e9f1b52"
down_revision = "f4b8c2d6e195"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("content_item", sa.Column("external_ref", sa.String(length=120), nullable=True))
    op.add_column("content_item", sa.Column("import_hash", sa.String(length=64), nullable=True))
    op.create_index(
        "uq_content_item_external_ref",
        "content_item",
        ["kind", "external_ref"],
        unique=True,
        postgresql_where=sa.text("external_ref is not null"),
    )
    op.create_table(
        "content_import_batch",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("format", sa.String(length=8), nullable=False),
        sa.Column("filename", sa.String(length=200), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.SmallInteger(), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("counts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status in ('previewed','committed','discarded')", name="content_import_batch_status"),
        sa.CheckConstraint("format in ('json','csv')", name="content_import_batch_format"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_content_import_batch_created_by"), "content_import_batch", ["created_by"], unique=False)
    op.create_table(
        "content_import_row",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("batch_id", sa.UUID(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=120), nullable=True),
        sa.Column("action", sa.String(length=10), nullable=False),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=True),
        sa.Column("item_id", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            "action in ('create','update','unchanged','skip','error')", name="content_import_row_action"
        ),
        sa.ForeignKeyConstraint(["batch_id"], ["content_import_batch.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["content_item.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "row_number", name="uq_content_import_row"),
    )
    op.create_index(op.f("ix_content_import_row_batch_id"), "content_import_row", ["batch_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_content_import_row_batch_id"), table_name="content_import_row")
    op.drop_table("content_import_row")
    op.drop_index(op.f("ix_content_import_batch_created_by"), table_name="content_import_batch")
    op.drop_table("content_import_batch")
    op.drop_index("uq_content_item_external_ref", table_name="content_item")
    op.drop_column("content_item", "import_hash")
    op.drop_column("content_item", "external_ref")
