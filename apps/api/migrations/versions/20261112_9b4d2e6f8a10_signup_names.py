"""First name and surname asked for at sign-up (AUTH-PASSWORD-01, owner 2026-11-11).

Nullable: older accounts have none. `display_name` stays and is set to "first name + surname" at sign-up.

Revision ID: 9b4d2e6f8a10
Revises: 7e3a9c1d5b20
Create Date: 2026-11-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "9b4d2e6f8a10"
down_revision = "7e3a9c1d5b20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_user", sa.Column("first_name", sa.String(60), nullable=True))
    op.add_column("app_user", sa.Column("surname", sa.String(60), nullable=True))


def downgrade() -> None:
    op.drop_column("app_user", "surname")
    op.drop_column("app_user", "first_name")
