"""Role → permission matrix (roadmap §4). Authorisation is decided on the server for every operation; hiding a menu
is never security. Some permissions additionally require a multi-factor-authenticated session (P04.S2.T2)."""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    student = "student"  # implicit for every authenticated account; never granted as a staff role
    content_author = "content_author"
    subject_reviewer = "subject_reviewer"
    academic_adjudicator = "academic_adjudicator"
    publisher = "publisher"
    support = "support"
    finance = "finance"
    platform_operator = "platform_operator"
    owner_admin = "owner_admin"


STAFF_ROLES = frozenset(r for r in Role if r is not Role.student)


class Permission(StrEnum):
    read_own_account = "read_own_account"
    edit_own_profile = "edit_own_profile"
    draft_content = "draft_content"
    review_content = "review_content"
    adjudicate = "adjudicate"
    publish_content = "publish_content"
    quarantine_content = "quarantine_content"
    view_support_context = "view_support_context"
    finance_operations = "finance_operations"
    operate_platform = "operate_platform"
    manage_roles = "manage_roles"
    view_audit = "view_audit"
    confirm_source_rights = "confirm_source_rights"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.student: frozenset({Permission.read_own_account, Permission.edit_own_profile}),
    Role.content_author: frozenset({Permission.draft_content}),
    Role.subject_reviewer: frozenset({Permission.review_content}),
    Role.academic_adjudicator: frozenset({Permission.adjudicate, Permission.review_content}),
    Role.publisher: frozenset({Permission.publish_content, Permission.quarantine_content}),
    Role.support: frozenset({Permission.view_support_context}),
    Role.finance: frozenset({Permission.finance_operations}),
    Role.platform_operator: frozenset({Permission.operate_platform}),
    Role.owner_admin: frozenset({Permission.manage_roles, Permission.view_audit, Permission.confirm_source_rights}),
}

# Sensitive operations need an MFA session (roadmap P04.S2.T2: publishing, finance, quarantine/regrade, administration).
MFA_REQUIRED: frozenset[Permission] = frozenset(
    {
        Permission.publish_content,
        Permission.quarantine_content,
        Permission.adjudicate,
        Permission.finance_operations,
        Permission.operate_platform,
        Permission.manage_roles,
        Permission.view_audit,
        Permission.confirm_source_rights,
    }
)


def permissions_for(roles: set[Role]) -> frozenset[Permission]:
    perms: set[Permission] = set(ROLE_PERMISSIONS[Role.student])
    for role in roles:
        perms |= ROLE_PERMISSIONS[role]
    return frozenset(perms)
