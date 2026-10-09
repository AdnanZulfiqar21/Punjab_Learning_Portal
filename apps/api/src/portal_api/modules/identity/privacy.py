"""Self-service data access and deletion requests (roadmap P18.S3.T2; PRIVACY-01).

**Export:** a signed-in person can download the data the portal holds about them as JSON. It covers their account
and profile, consents, sessions, trial and access records, allowance ledger, practice attempts with answers and
scores, written attempts with their released results, help requests (without staff-only notes), notifications and
preferences, and support's assisted access to their activity. It excludes secrets and anti-abuse identifiers
(password and token hashes, installation references, provider evidence) and other people's data. Every export is
audited.

**Deletion:** a request is recorded and routed to support as an account request, with an audit record. Nothing is
erased automatically. What must be deleted, anonymised or retained (trial-evidence rules, allowance ledger,
appeal holds, backups) needs the approved privacy and retention schedule (BLOCKERS B15, P18.S3.T3).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from portal_api.errors import Conflict, Unprocessable
from portal_api.modules.audit.models import record
from portal_api.modules.identity.models import AppUser

# Columns never exported: secrets, anti-abuse identifiers and provider evidence.
_STAFF = ("author_id", "assessor_id", "staff_id")  # other people (staff) are never identified in the export
_EXCLUDED = ("hash", "token", "secret", "installation_ref", "evidence", "pepper", "storage_key", "provider_ref")


# Every table holding one person's rows is either exported or excluded here with the reason (OCT9 coverage
# inventory; `tests/test_privacy.py` fails when a new per-person table is in neither list).
EXPORTED_TABLES = frozenset(
    {
        "allowance_event", "attempt", "consent_record", "entitlement", "lesson_completion", "mistake_entry",
        "mock_accommodation", "notification", "notification_preference", "practice_form", "student_profile",
        "support_assisted_access", "support_ticket", "trial_claim", "trial_device_use", "trial_exception",
        "trial_grant", "user_session", "written_attempt", "written_form", "written_notice", "written_recheck_request",
    }
)  # fmt: skip
NOT_EXPORTED = {
    "dev_credential": "a development-only sign-in secret",
    "push_token": "a device delivery secret",
    "notification_delivery": "provider delivery log; the notifications themselves are exported",
    "staff_role_grant": "staff authorisation, not learner data",
    "written_regrade_job": "a staff-requested processing job",
}


def _row(obj: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for col in inspect(obj).mapper.column_attrs:
        if any(x in col.key for x in _EXCLUDED) or col.key.endswith("_by") or col.key in _STAFF:
            continue
        value = getattr(obj, col.key)
        out[col.key] = value.isoformat() if isinstance(value, datetime) else value
    return out


def _rows(db: Session, model: Any, *where: Any) -> list[dict[str, Any]]:
    return [_row(o) for o in db.scalars(select(model).where(*where))]


def export(db: Session, user: AppUser) -> tuple[bytes, str]:
    from portal_api.modules.access.models import AllowanceEvent, Entitlement, TrialGrant
    from portal_api.modules.access.trial_devices import TrialClaim, TrialDeviceUse, TrialException
    from portal_api.modules.assessment import notebook
    from portal_api.modules.assessment.models import Attempt, AttemptAnswer, PracticeForm, ScoreVersion
    from portal_api.modules.assessment.notebook import MistakeEntry
    from portal_api.modules.assessment.sessions import MockAccommodation, held_forms
    from portal_api.modules.content.completion import LessonCompletion
    from portal_api.modules.identity.models import ConsentRecord, StudentProfile
    from portal_api.modules.identity.sessions import UserSession
    from portal_api.modules.notifications.models import Notification, NotificationPreference
    from portal_api.modules.support.models import (
        SupportAssistedAccess,
        SupportAttachment,
        SupportMessage,
        SupportTicket,
    )
    from portal_api.modules.written.adjudication import WrittenNotice
    from portal_api.modules.written.models import WrittenAttempt, WrittenForm
    from portal_api.modules.written.review import WrittenRecheckRequest, WrittenScoreVersion

    uid = user.id
    notebook.sync(db, uid)
    held = held_forms(db, uid)
    attempt_forms = db.execute(select(Attempt.id, Attempt.form_id).where(Attempt.user_id == uid)).all()
    attempts = [a for a, _ in attempt_forms]
    released = [a for a, f in attempt_forms if f not in held]
    written = list(db.scalars(select(WrittenAttempt.id).where(WrittenAttempt.user_id == uid)))
    tickets = list(db.scalars(select(SupportTicket.id).where(SupportTicket.user_id == uid)))
    data = {
        "format": "portal-personal-data-export",
        "schema_version": 2,
        "exported_at": datetime.now(UTC).isoformat(),
        "account": _row(user),
        "profile": _rows(db, StudentProfile, StudentProfile.user_id == uid),
        "consents": _rows(db, ConsentRecord, ConsentRecord.user_id == uid),
        "sessions": _rows(db, UserSession, UserSession.user_id == uid),
        "trial": {
            "grants": _rows(db, TrialGrant, TrialGrant.user_id == uid),
            "claims": _rows(db, TrialClaim, TrialClaim.user_id == uid),
            "devices": _rows(db, TrialDeviceUse, TrialDeviceUse.user_id == uid),
            "exceptions": _rows(db, TrialException, TrialException.user_id == uid),
        },
        "access": _rows(db, Entitlement, Entitlement.user_id == uid),
        "written_allowance": _rows(db, AllowanceEvent, AllowanceEvent.user_id == uid),
        "practice": {
            "forms": _rows(db, PracticeForm, PracticeForm.owner_id == uid),
            "attempts": _rows(db, Attempt, Attempt.user_id == uid),
            "answers": _rows(db, AttemptAnswer, AttemptAnswer.attempt_id.in_(attempts)) if attempts else [],
            # OCT9-01: a held scheduled mock's scores (marks, correctness, corrected keys) are exported once released
            "scores": _rows(db, ScoreVersion, ScoreVersion.attempt_id.in_(released)) if released else [],
            "results_pending": [
                {"attempt_id": str(a), "available_at": at.isoformat() if at else None}
                for a, f in attempt_forms
                if f in held
                for at in [held[f]]
            ],
            "notebook": _rows(db, MistakeEntry, MistakeEntry.user_id == uid),
            "mock_accommodations": _rows(db, MockAccommodation, MockAccommodation.user_id == uid),
        },
        "lesson_completions": _rows(db, LessonCompletion, LessonCompletion.user_id == uid),
        "written": {
            "forms": _rows(db, WrittenForm, WrittenForm.owner_id == uid),
            "attempts": _rows(db, WrittenAttempt, WrittenAttempt.user_id == uid),
            "notices": _rows(db, WrittenNotice, WrittenNotice.user_id == uid),
            "recheck_requests": _rows(db, WrittenRecheckRequest, WrittenRecheckRequest.requested_by == uid),
            "released_results": _rows(
                db,
                WrittenScoreVersion,
                WrittenScoreVersion.attempt_id.in_(written),
                WrittenScoreVersion.released.is_(True),
            )
            if written
            else [],
        },
        "help_requests": {
            "requests": _rows(db, SupportTicket, SupportTicket.user_id == uid),
            "messages": _rows(
                db, SupportMessage, SupportMessage.ticket_id.in_(tickets), SupportMessage.internal.is_(False)
            )
            if tickets
            else [],
            "screenshots": _rows(db, SupportAttachment, SupportAttachment.ticket_id.in_(tickets)) if tickets else [],
            "assisted_access": _rows(db, SupportAssistedAccess, SupportAssistedAccess.user_id == uid),
        },
        "notifications": _rows(db, Notification, Notification.user_id == uid),
        "notification_preferences": _rows(db, NotificationPreference, NotificationPreference.user_id == uid),
    }
    # Staff notes never reach the person: drop escalation notes from their own requests.
    for t in data["help_requests"]["requests"]:  # type: ignore[index]
        for k in ("escalated_by", "escalation_reason"):
            t.pop(k, None)
    body = json.dumps(data, ensure_ascii=False, indent=1, default=str).encode("utf-8")
    record(
        db,
        actor=uid,
        action="privacy.data_exported",
        target_type="app_user",
        target_id=str(uid),
        details={"bytes": len(body)},
    )
    db.commit()
    return body, f"my-data-{datetime.now(UTC):%Y%m%d}.json"


def request_deletion(db: Session, user: AppUser, confirm_email: str, reason: str | None) -> uuid.UUID:
    """Record a deletion request and route it to support. Nothing is erased automatically (B15)."""
    from portal_api.modules.support.models import SupportMessage, SupportTicket

    if not user.email or confirm_email.strip().lower() != user.email.lower():
        raise Unprocessable("Type the email address of this account to confirm.")
    open_request = db.scalar(
        select(SupportTicket.id).where(
            SupportTicket.user_id == user.id,
            SupportTicket.subject == "Account deletion request",
            SupportTicket.status != "resolved",
        )
    )
    if open_request is not None:
        raise Conflict("You already have an open deletion request.", ticket_id=str(open_request))
    t = SupportTicket(id=uuid.uuid4(), user_id=user.id, category="account", subject="Account deletion request")
    db.add(t)
    db.flush()
    db.add(
        SupportMessage(
            ticket_id=t.id,
            author_id=user.id,
            body="Please delete my account and personal data."
            + (f"\n\nReason: {reason.strip()}" if reason and reason.strip() else ""),
        )
    )
    record(
        db,
        actor=user.id,
        action="privacy.deletion_requested",
        target_type="app_user",
        target_id=str(user.id),
        details={"ticket": str(t.id)},
    )
    db.commit()
    return t.id
