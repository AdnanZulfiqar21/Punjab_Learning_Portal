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
    grant_entitlements = "grant_entitlements"
    review_trial_eligibility = "review_trial_eligibility"  # §16.7: private shared-device review and exceptions
    manage_help = "manage_help"  # P15.S2: draft help articles (publishing also needs MFA)
    look_up_learners = "look_up_learners"  # P15.S3.T3: learner lookup, redacted timeline, assisted access
    manage_exam_profiles = "manage_exam_profiles"  # P05.S3: draft, verify (two people) and publish exam profiles


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.student: frozenset({Permission.read_own_account, Permission.edit_own_profile}),
    Role.content_author: frozenset({Permission.draft_content}),
    Role.subject_reviewer: frozenset({Permission.review_content}),
    Role.academic_adjudicator: frozenset(
        {Permission.adjudicate, Permission.review_content, Permission.manage_exam_profiles}
    ),
    Role.publisher: frozenset({Permission.publish_content, Permission.quarantine_content}),
    Role.support: frozenset(
        {
            Permission.view_support_context,
            Permission.review_trial_eligibility,
            Permission.manage_help,
            Permission.look_up_learners,
        }
    ),
    Role.finance: frozenset({Permission.finance_operations, Permission.grant_entitlements}),
    Role.platform_operator: frozenset({Permission.operate_platform}),
    Role.owner_admin: frozenset(
        {
            Permission.manage_roles,
            Permission.view_audit,
            Permission.confirm_source_rights,
            Permission.grant_entitlements,
            Permission.manage_exam_profiles,
        }
    ),
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
        Permission.grant_entitlements,
        Permission.review_trial_eligibility,
        Permission.look_up_learners,
        Permission.manage_exam_profiles,
    }
)


def permissions_for(roles: set[Role]) -> frozenset[Permission]:
    perms: set[Permission] = set(ROLE_PERMISSIONS[Role.student])
    for role in roles:
        perms |= ROLE_PERMISSIONS[role]
    return frozenset(perms)
