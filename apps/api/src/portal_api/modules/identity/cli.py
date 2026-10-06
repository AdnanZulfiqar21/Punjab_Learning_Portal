"""Operator command to bootstrap the first administrator (nobody holds manage_roles before that).

    portal-grant-role --email owner@example.org --role owner_admin --reason "initial owner account"

The person must already have signed in once (so their account exists). The grant is audited with actor=None and
via=cli. Every later grant goes through the MFA-protected admin API.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from portal_api.db import get_sessionmaker
from portal_api.modules.audit.models import record
from portal_api.modules.identity.models import AppUser, StaffRoleGrant
from portal_api.modules.identity.permissions import STAFF_ROLES, Role


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--email", required=True)
    ap.add_argument("--role", required=True, choices=sorted(r.value for r in STAFF_ROLES))
    ap.add_argument("--reason", required=True)
    args = ap.parse_args(argv)
    with get_sessionmaker()() as db:
        users = db.scalars(select(AppUser).where(AppUser.email == args.email.lower())).all()
        if len(users) != 1:
            print(f"expected exactly one account with email {args.email}, found {len(users)}", file=sys.stderr)
            return 1
        user = users[0]
        grant = StaffRoleGrant(
            user_id=user.id, role=Role(args.role).value, scope={}, granted_by=None, reason=args.reason
        )
        db.add(grant)
        db.flush()
        record(
            db,
            actor=None,
            action="role.grant",
            target_type="app_user",
            target_id=str(user.id),
            details={"grant_id": str(grant.id), "role": args.role, "reason": args.reason, "via": "cli"},
        )
        db.commit()
        print(f"granted {args.role} to {user.id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
