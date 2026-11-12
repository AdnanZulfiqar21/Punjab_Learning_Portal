"""The portal's own email + password sign-up with email verification codes (AUTH-PASSWORD-01).

The email + password records stay in `dev_credential` (the model is PasswordCredential; renaming the table would break
the previous build during a rolling deploy) and gain `email_verified_at`. Existing rows are development accounts
registered before verification existed; they are marked verified so they keep signing in. Adds `email_code` for the
6-digit codes (hashes only) `app_user.phone` and `app_user.date_of_birth` (asked for at sign-up, not verified; nullable for older
accounts).

Revision ID: 7e3a9c1d5b20
Revises: 5c9e1d7a2b40
Create Date: 2026-11-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "7e3a9c1d5b20"
down_revision = "5c9e1d7a2b40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_user", sa.Column("phone", sa.String(20), nullable=True))
    op.add_column("app_user", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("dev_credential", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("update dev_credential set email_verified_at = now()")
    op.create_table(
        "email_code",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("purpose in ('verify_email')", name="email_code_purpose"),
    )
    op.create_index("ix_email_code_user_purpose", "email_code", ["user_id", "purpose", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_email_code_user_purpose", table_name="email_code")
    op.drop_table("email_code")
    op.drop_column("dev_credential", "email_verified_at")
    op.drop_column("app_user", "date_of_birth")
    op.drop_column("app_user", "phone")
