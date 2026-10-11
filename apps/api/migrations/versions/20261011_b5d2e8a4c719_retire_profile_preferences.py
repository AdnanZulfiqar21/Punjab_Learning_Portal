"""student_profile.preferences gets a default before it is dropped (P18.S3.T1, MINIMISATION-01)

The code no longer maps this never-used free-form column. Old code still inserts it, and new code can only insert
without it once the database supplies a default, so this release adds the default (expand) and a later release
drops the column (contract).

Revision ID: b5d2e8a4c719
Revises: e8b2d6f4a193
Create Date: 2026-10-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b5d2e8a4c719"
down_revision = "e8b2d6f4a193"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("student_profile", "preferences", server_default=sa.text("'{}'::jsonb"))


def downgrade() -> None:
    op.alter_column("student_profile", "preferences", server_default=None)
