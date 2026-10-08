"""Development/test-only staff fixtures for exercising the content studio locally and in CI end-to-end tests.

    portal-dev-seed-staff            # idempotent; prints the accounts it ensured

Creates development-adapter accounts (email + password) with *scoped* content roles for Class XI Biology. These are
technical fixtures: they are not reviewers, they confer no academic approval, and nothing they approve can reach
learners while publication rights stay UNVERIFIED. The command refuses to run unless the role is development or
test and the development identity adapter is enabled (both are refused in staging/production by the config validator).
"""

from __future__ import annotations

import sys

from argon2 import PasswordHasher
from sqlalchemy import select

from portal_api.config import get_settings
from portal_api.db import get_sessionmaker
from portal_api.modules.audit.models import record
from portal_api.modules.identity.models import AppUser, DevCredential, StaffRoleGrant

# Development-only fixture password for the local identity adapter. Never valid anywhere else.
FIXTURE_PASSWORD = "studio-fixture-pass-1"  # noqa: S105 - dev-adapter fixture, refused outside development/test
SCOPE = {"grades": [11], "subjects": ["biology"]}
FIXTURES: list[tuple[str, list[str]]] = [
    ("studio-author@example.com", ["content_author"]),
    ("studio-author2@example.com", ["content_author"]),
    ("studio-reviewer@example.com", ["subject_reviewer"]),
    ("studio-reviewer2@example.com", ["subject_reviewer"]),  # independent rechecks need a second marker
    ("studio-publisher@example.com", ["publisher"]),
    ("studio-support@example.com", ["support"]),
]


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    if settings.role not in ("development", "test") or not settings.dev_auth_enabled:
        print("refusing: staff fixtures exist only for development/test with the dev identity adapter", file=sys.stderr)
        return 2
    hasher = PasswordHasher()
    with get_sessionmaker()() as db:
        for email, roles in FIXTURES:
            user = db.scalar(select(AppUser).where(AppUser.email == email))
            if user is None:
                user = AppUser(
                    issuer=settings.dev_auth_issuer,
                    subject=f"dev|{email}",
                    email=email,
                    display_name=email.split("@")[0],
                )
                db.add(user)
                db.flush()
                db.add(DevCredential(user_id=user.id, email=email, password_hash=hasher.hash(FIXTURE_PASSWORD)))
            for role in roles:
                held = db.scalar(
                    select(StaffRoleGrant).where(
                        StaffRoleGrant.user_id == user.id,
                        StaffRoleGrant.role == role,
                        StaffRoleGrant.revoked_at.is_(None),
                    )
                )
                if held is None:
                    grant = StaffRoleGrant(
                        user_id=user.id,
                        role=role,
                        scope=SCOPE,
                        granted_by=None,
                        reason="development fixture (portal-dev-seed-staff)",
                    )
                    db.add(grant)
                    db.flush()
                    record(
                        db,
                        actor=None,
                        action="role.grant",
                        target_type="app_user",
                        target_id=str(user.id),
                        details={"grant_id": str(grant.id), "role": role, "scope": SCOPE, "via": "dev-seed"},
                    )
            print(f"{email}: {', '.join(roles)} (Class XI Biology)")
        db.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
