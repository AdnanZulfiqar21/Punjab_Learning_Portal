"""Password reset codes (AUTH-PASSWORD-01, owner 2026-11-12): `email_code.purpose` may also be `reset_password`.

Revision ID: c3f1a7e9d520
Revises: 9b4d2e6f8a10
Create Date: 2026-11-12
"""

from __future__ import annotations

from alembic import op

revision = "c3f1a7e9d520"
down_revision = "9b4d2e6f8a10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("email_code_purpose", "email_code", type_="check")
    op.create_check_constraint("email_code_purpose", "email_code", "purpose in ('verify_email','reset_password')")


def downgrade() -> None:
    op.execute("delete from email_code where purpose = 'reset_password'")
    op.drop_constraint("email_code_purpose", "email_code", type_="check")
    op.create_check_constraint("email_code_purpose", "email_code", "purpose in ('verify_email')")
