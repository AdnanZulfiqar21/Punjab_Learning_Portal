"""content_import_batch.format accepts 'xlsx' (P06.S2.T1, IMPORT-XLSX-01)

Widens one check constraint; no column or type changes, and the previous build never writes 'xlsx'.

Rollback note: the previous build's import list only knows 'json' and 'csv'. An xlsx batch holds exactly the CSV
template's rows, so before running an earlier build, relabel them:
`UPDATE content_import_batch SET format = 'csv' WHERE format = 'xlsx';` (recorded in DECISIONS, IMPORT-XLSX-01).

Revision ID: 219df9c8c75c
Revises: 6b024866201d
Create Date: 2026-10-14
"""

from __future__ import annotations

from alembic import op

revision = "219df9c8c75c"
down_revision = "6b024866201d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("content_import_batch_format", "content_import_batch", type_="check")
    op.create_check_constraint("content_import_batch_format", "content_import_batch", "format in ('json','csv','xlsx')")


def downgrade() -> None:
    op.execute("UPDATE content_import_batch SET format = 'csv' WHERE format = 'xlsx'")
    op.drop_constraint("content_import_batch_format", "content_import_batch", type_="check")
    op.create_check_constraint("content_import_batch_format", "content_import_batch", "format in ('json','csv')")
