"""content_import_batch: bulk imports checked and committed by the import worker (P06.S2.T1, IMPORT-BULK-01)

Six nullable columns (row progress, the private upload's key, a failure reason, the worker lease) and four more
statuses: queued, validating, committing, failed. The previous build never writes these statuses and leaves the new
columns null.

Rollback note: the previous build's import list only knows previewed/committed/discarded. Before running it, end the
batches it can't show (none of them has written content):
`UPDATE content_import_batch SET status = 'discarded' WHERE status IN ('queued','validating','committing','failed');`
(recorded in DECISIONS, IMPORT-BULK-01; the downgrade does the same).

Revision ID: 8d67f124450b
Revises: 3c0d0a813dc8
Create Date: 2026-10-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "8d67f124450b"
down_revision = "3c0d0a813dc8"
branch_labels = None
depends_on = None

OLD = "status in ('previewed','committed','discarded')"
NEW = "status in ('queued','validating','previewed','committing','committed','discarded','failed')"


def upgrade() -> None:
    op.add_column("content_import_batch", sa.Column("rows_total", sa.Integer(), nullable=True))
    op.add_column("content_import_batch", sa.Column("rows_checked", sa.Integer(), nullable=True))
    op.add_column("content_import_batch", sa.Column("file_key", sa.Text(), nullable=True))
    op.add_column("content_import_batch", sa.Column("failure", sa.Text(), nullable=True))
    op.add_column("content_import_batch", sa.Column("lease_owner", sa.String(length=120), nullable=True))
    op.add_column("content_import_batch", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.drop_constraint("content_import_batch_status", "content_import_batch", type_="check")
    op.create_check_constraint("content_import_batch_status", "content_import_batch", NEW)


def downgrade() -> None:
    op.execute(
        "UPDATE content_import_batch SET status = 'discarded' "
        "WHERE status IN ('queued','validating','committing','failed')"
    )
    op.drop_constraint("content_import_batch_status", "content_import_batch", type_="check")
    op.create_check_constraint("content_import_batch_status", "content_import_batch", OLD)
    for column in ("lease_expires_at", "lease_owner", "failure", "file_key", "rows_checked", "rows_total"):
        op.drop_column("content_import_batch", column)
