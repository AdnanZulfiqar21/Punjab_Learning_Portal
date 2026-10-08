"""written files and logical pages (review R01/R02)

Splits uploaded originals (`written_file`) from logical pages (`written_page`): a photo is one page, a PDF has one page
per PDF page, and the page cap and answer mapping count logical pages. Existing rows keep their ids as page 1 of a file
with the same id, so existing manifests and receipts still resolve. Multi-page PDFs from before this change get pages 2+
with new ids. Previews are generated afterwards by `portal-written-previews` (never inside a migration).

Revision ID: 648941e093b0
Revises: 1bc0b73fea5b
Create Date: 2026-10-08

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "648941e093b0"
down_revision: str | Sequence[str] | None = "1bc0b73fea5b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "written_file",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("attempt_id", sa.UUID(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(length=40), nullable=False),
        sa.Column("page_count", sa.SmallInteger(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.CheckConstraint("status in ('uploaded','withdrawn')", name="written_file_status"),
        sa.ForeignKeyConstraint(["attempt_id"], ["written_attempt.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_id", "sha256", name="uq_written_file_attempt_hash"),
    )
    op.create_index(op.f("ix_written_file_attempt_id"), "written_file", ["attempt_id"], unique=False)
    op.execute(
        "insert into written_file (id, attempt_id, storage_key, sha256, size, content_type, page_count, uploaded_at, "
        "status) select id, attempt_id, storage_key, sha256, size, content_type, pdf_pages, uploaded_at, status "
        "from written_page"
    )
    op.add_column("written_page", sa.Column("file_id", sa.UUID(), nullable=True))
    op.add_column("written_page", sa.Column("page_index", sa.SmallInteger(), nullable=True))
    op.add_column("written_page", sa.Column("preview_key", sa.Text(), nullable=True))
    op.add_column("written_page", sa.Column("preview_sha256", sa.String(length=64), nullable=True))
    op.execute("update written_page set file_id = id, page_index = 1")
    op.execute(
        "insert into written_page (id, attempt_id, file_id, page_index, uploaded_at, status) "
        "select gen_random_uuid(), f.attempt_id, f.id, g.n, f.uploaded_at, f.status "
        "from written_file f cross join lateral generate_series(2, f.page_count) as g(n) where f.page_count > 1"
    )
    op.alter_column("written_page", "file_id", nullable=False)
    op.alter_column("written_page", "page_index", nullable=False)
    op.create_foreign_key(
        "written_page_file_id_fkey", "written_page", "written_file", ["file_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_index(op.f("ix_written_page_file_id"), "written_page", ["file_id"], unique=False)
    op.create_unique_constraint("uq_written_page_file_index", "written_page", ["file_id", "page_index"])
    op.drop_constraint("uq_written_page_attempt_hash", "written_page", type_="unique")
    for col in ("storage_key", "sha256", "size", "content_type", "pdf_pages", "after_cutoff"):
        op.drop_column("written_page", col)
    op.add_column(
        "written_receipt",
        sa.Column("preview_hashes", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
    )


def downgrade() -> None:
    """Lossy by necessity: pages 2+ of multi-page PDFs are dropped; their files keep the original bytes."""
    op.drop_column("written_receipt", "preview_hashes")
    op.add_column("written_page", sa.Column("storage_key", sa.Text(), nullable=True))
    op.add_column("written_page", sa.Column("sha256", sa.String(length=64), nullable=True))
    op.add_column("written_page", sa.Column("size", sa.Integer(), nullable=True))
    op.add_column("written_page", sa.Column("content_type", sa.String(length=40), nullable=True))
    op.add_column("written_page", sa.Column("pdf_pages", sa.SmallInteger(), nullable=True))
    op.add_column("written_page", sa.Column("after_cutoff", sa.Boolean(), server_default="false", nullable=False))
    op.execute("delete from written_page where page_index > 1")
    op.execute(
        "update written_page p set storage_key = f.storage_key, sha256 = f.sha256, size = f.size, "
        "content_type = f.content_type, pdf_pages = f.page_count from written_file f where f.id = p.file_id"
    )
    for col in ("storage_key", "sha256", "size", "content_type", "pdf_pages"):
        op.alter_column("written_page", col, nullable=False)
    op.create_unique_constraint("uq_written_page_attempt_hash", "written_page", ["attempt_id", "sha256"])
    op.drop_constraint("uq_written_page_file_index", "written_page", type_="unique")
    op.drop_index(op.f("ix_written_page_file_id"), table_name="written_page")
    op.drop_constraint("written_page_file_id_fkey", "written_page", type_="foreignkey")
    for col in ("file_id", "page_index", "preview_key", "preview_sha256"):
        op.drop_column("written_page", col)
    op.drop_index(op.f("ix_written_file_attempt_id"), table_name="written_file")
    op.drop_table("written_file")
