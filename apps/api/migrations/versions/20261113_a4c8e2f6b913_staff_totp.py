"""Two-step sign-in with an authenticator app (STAFF-MFA-01): authenticator secrets, recovery codes, and when a
session proved its second factor.

Revision ID: a4c8e2f6b913
Revises: c3f1a7e9d520
Create Date: 2026-11-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a4c8e2f6b913"
down_revision = "c3f1a7e9d520"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "totp_credential",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("secret_enc", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_step", sa.BigInteger(), nullable=True),
        sa.Column("failed_attempts", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "totp_recovery_code",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_totp_recovery_code_user_id", "totp_recovery_code", ["user_id"])
    op.add_column("user_session", sa.Column("mfa_verified_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("user_session", "mfa_verified_at")
    op.drop_index("ix_totp_recovery_code_user_id", table_name="totp_recovery_code")
    op.drop_table("totp_recovery_code")
    op.drop_table("totp_credential")
