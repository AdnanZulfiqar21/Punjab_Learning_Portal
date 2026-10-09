"""Learner practice and attempt API (P09/P10). All responses are private (`no-store`)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from portal_api.db import get_session
from portal_api.errors import Conflict, NotFound
from portal_api.modules.assessment import attempts, forms
from portal_api.modules.assessment.models import Attempt, PracticeForm, SubmissionReceipt
from portal_api.modules.assessment.schemas import (
    AnswerOut,
    AttemptOut,
    AvailabilityOut,
    ChapterAvailability,
    FormCreateIn,
    FormOut,
    ItemReview,
    ItemSnapshot,
    OpIn,
    OpResult,
    OpsIn,
    ReceiptOut,
    ResultOut,
    RevealOut,
    SaveOut,
    SubmitIn,
    SubmitOut,
)
from portal_api.modules.identity.deps import CurrentPrincipal, Principal, require
from portal_api.modules.identity.permissions import Permission
from portal_api.modules.system import operations

router = APIRouter(prefix="/v1", tags=["practice"])
DB = Annotated[Session, Depends(get_session)]


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


def _ops(items: list[OpIn]) -> list[attempts.Op]:
    return [attempts.Op(op_id=o.op_id, position=o.position, revision=o.revision, option_id=o.option_id) for o in items]


def _form_out(f: PracticeForm) -> FormOut:
    return FormOut(
        id=f.id,
        grade=f.grade_number,
        subject=f.subject_code,
        scope=f.scope,
        question_count=f.question_count,
        duration_s=f.duration_s,
        late_write_tolerance_ms=f.late_write_tolerance_ms,
        feedback_mode=f.feedback_mode,  # type: ignore[arg-type]
        negative_marks=f.negative_marks,
        created_at=f.created_at,
    )


def _receipt_out(r: SubmissionReceipt) -> ReceiptOut:
    return ReceiptOut(
        id=r.id,
        reason=r.reason,  # type: ignore[arg-type]
        admitted_at=r.admitted_at,
        answered_count=r.answered_count,
        question_count=r.question_count,
        ledger_hash=r.ledger_hash,
    )


def _attempt_out(db: Session, a: Attempt) -> AttemptOut:
    form = db.get(PracticeForm, a.form_id)
    assert form is not None
    receipt = attempts.receipt_for(db, a.id)
    return AttemptOut(
        id=a.id,
        form_id=a.form_id,
        status=a.status,  # type: ignore[arg-type]
        started_at=a.started_at,
        deadline_at=a.deadline_at,
        cutoff_at=a.cutoff_at,
        tolerance_ms=a.tolerance_ms,
        server_now=attempts.db_now(db),
        feedback_mode=form.feedback_mode,  # type: ignore[arg-type]
        items=[ItemSnapshot(**i) for i in forms.learner_items(db, form)],
        answers=[AnswerOut(**x) for x in attempts.answers_view(db, a)],
        receipt=_receipt_out(receipt) if receipt else None,
    )


@router.get("/practice/availability", response_model=AvailabilityOut, summary="Approved questions per chapter")
def availability(
    db: DB,
    _: CurrentPrincipal,
    response: Response,
    grade: Annotated[int, Query(ge=11, le=12)],
    subject: Annotated[str, Query(min_length=2, max_length=40)],
) -> AvailabilityOut:
    _private(response)
    rows = forms.availability(db, grade, subject)
    return AvailabilityOut(grade=grade, subject=subject, chapters=[ChapterAvailability(**r) for r in rows])


@router.post(
    "/practice/forms",
    response_model=FormOut,
    status_code=201,
    summary="Generate and freeze a practice test",
    dependencies=[Depends(operations.requires("new_practice_tests"))],
)
def create_form(
    db: DB,
    who: CurrentPrincipal,
    body: FormCreateIn,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=80)],
) -> FormOut:
    _private(response)
    form = forms.create_form(
        db,
        who,
        idempotency_key=idempotency_key,
        grade=body.grade,
        subject=body.subject,
        scope_mode=body.scope,
        half=body.half,
        chapter_ids=body.chapter_ids,
        topic_ids=body.topic_ids,
        question_count=body.question_count,
        timed_minutes=body.timed_minutes,
        feedback_mode=body.feedback_mode,
    )
    return _form_out(form)


@router.post("/practice/forms/{form_id}/attempt", response_model=AttemptOut, summary="Start (or resume) the attempt")
def start_attempt(db: DB, who: CurrentPrincipal, form_id: uuid.UUID, response: Response) -> AttemptOut:
    _private(response)
    attempt = attempts.start(db, who, form_id)
    return _attempt_out(db, attempts.load(db, who, attempt.id))


@router.get("/attempts/{attempt_id}", response_model=AttemptOut, summary="Resume: questions, saved answers, timing")
def get_attempt(db: DB, who: CurrentPrincipal, attempt_id: uuid.UUID, response: Response) -> AttemptOut:
    _private(response)
    return _attempt_out(db, attempts.load(db, who, attempt_id))


@router.post("/attempts/{attempt_id}/answers", response_model=SaveOut, summary="Save answer operations (§10.5)")
def save_answers(db: DB, who: CurrentPrincipal, attempt_id: uuid.UUID, body: OpsIn, response: Response) -> SaveOut:
    _private(response)
    out = attempts.save(db, who, attempt_id, _ops(body.ops))
    return SaveOut(status=out["status"], results=[OpResult(**r) for r in out["results"]], receipt_id=out["receipt_id"])


@router.post("/attempts/{attempt_id}/submit", response_model=SubmitOut, summary="Final submission (idempotent)")
def submit(db: DB, who: CurrentPrincipal, attempt_id: uuid.UUID, body: SubmitIn, response: Response) -> SubmitOut:
    _private(response)
    out = attempts.submit(db, who, attempt_id, body.idempotency_key, _ops(body.ops))
    return SubmitOut(
        receipt=_receipt_out(out["receipt"]),
        same_request=out["same_request"],
        reconciliation=[OpResult(**r) for r in out["reconciliation"]],
    )


@router.post(
    "/attempts/{attempt_id}/items/{position}/reveal",
    response_model=RevealOut,
    summary="Immediate-feedback practice: check one saved answer (locks it)",
)
def reveal(db: DB, who: CurrentPrincipal, attempt_id: uuid.UUID, position: int, response: Response) -> RevealOut:
    _private(response)
    return RevealOut(**attempts.reveal(db, who, attempt_id, position))


@router.get("/attempts/{attempt_id}/result", response_model=ResultOut, summary="Score and review after submission")
def result(db: DB, who: CurrentPrincipal, attempt_id: uuid.UUID, response: Response) -> ResultOut:
    _private(response)
    attempt = attempts.load(db, who, attempt_id)
    if attempt.status != "finalised":
        raise Conflict("Results are available after you submit.")
    score = attempts.latest_score(db, attempt.id)
    receipt = attempts.receipt_for(db, attempt.id)
    form = db.get(PracticeForm, attempt.form_id)
    held = None
    scope = (form.scope or {}) if form is not None else {}
    if scope.get("session_id"):  # the session's current release time decides (staff may delay it for a correction)
        from portal_api.modules.assessment.sessions import MockSession

        session = db.get(MockSession, uuid.UUID(scope["session_id"]))
        held = session.results_at.isoformat() if session is not None else None
    if held and datetime.fromisoformat(held) > db.execute(select(func.now())).scalar_one():
        # SCHEDULE-01: a scheduled mock's results (and so its keys) stay private until the release time.
        raise Conflict(
            "Your answers are saved. Results are released after the mock window closes.",
            code_reason="RESULTS_PENDING",
            available_at=held,
        )
    if score is None or receipt is None or form is None:
        raise NotFound("The result is not available yet.")
    keys = forms.item_keys(db, form)
    rows = {r["position"]: r for r in score.items}
    items = []
    for fi in form.items:
        k = keys[fi.position]
        r = rows[fi.position]
        items.append(
            ItemReview(
                position=fi.position,
                marks=fi.marks,
                stem=k["stem"],
                options=[{"id": oid, "blocks": k["options"][oid]["blocks"]} for oid in fi.option_order],  # type: ignore[misc]
                chosen=r["chosen"],
                correct_option_id=r.get("corrected_key") or k["correct_option_id"],
                correct=r["correct"],
                earned=r["earned"],
                treatment=r["treatment"],
                explanation=k["explanation"],
            )
        )
    return ResultOut(
        attempt_id=attempt.id,
        version=score.version,
        status=score.status,  # type: ignore[arg-type]
        raw=score.raw,
        maximum=score.maximum,
        percentage=score.percentage,  # type: ignore[arg-type]
        answered=receipt.answered_count,
        question_count=receipt.question_count,
        finalise_reason=attempt.finalise_reason,  # type: ignore[arg-type]
        items=items,
        revised_at=score.created_at if score.version > 1 else None,
        revision_reason=score.reason if score.version > 1 else None,
    )


# ------------------------------------------------------------------ exam profiles (P05.S3, EXAMPROFILE-01)
class ExamProfileIn(BaseModel):
    code: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9-]+$")
    name: str = Field(min_length=3, max_length=200)
    eligibility_note: str = Field(default="", max_length=2000)


class ProfileVersionIn(BaseModel):
    year: int = Field(ge=2020, le=2100)
    rules: dict[str, Any]


class VerifyIn(BaseModel):
    note: str = Field(min_length=10, max_length=2000, description="What you checked against the official source")


class ProfileVersionOut(BaseModel):
    id: uuid.UUID
    version: int
    year: int
    status: Literal["draft", "verified", "published", "retired"]
    rules: dict[str, Any]
    total_questions: int
    verifications: int
    published_at: datetime | None


class ExamProfileOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    eligibility_note: str
    versions: list[ProfileVersionOut]


class PublishedProfileOut(BaseModel):
    code: str
    name: str
    eligibility_note: str
    version: int
    year: int
    duration_minutes: int
    total_questions: int
    sections: list[dict[str, Any]]
    source_url: str


def _pv(v: Any) -> ProfileVersionOut:
    from portal_api.modules.assessment import profiles

    return ProfileVersionOut(
        id=v.id,
        version=v.version,
        year=v.year,
        status=v.status,
        rules=v.rules,
        total_questions=profiles.total_questions(v.rules),
        verifications=len(v.verifications),
        published_at=v.published_at,
    )


def _profiles_out(db: Session) -> list[ExamProfileOut]:
    from portal_api.modules.assessment import profiles

    return [
        ExamProfileOut(
            id=p.id, code=p.code, name=p.name, eligibility_note=p.eligibility_note, versions=[_pv(v) for v in vs]
        )
        for p, vs in profiles.profiles(db)
    ]


ProfileManager = Annotated[Principal, Depends(require(Permission.manage_exam_profiles))]


@router.get("/admin/exam-profiles", response_model=list[ExamProfileOut], summary="Exam profiles and all versions")
def list_exam_profiles(db: DB, who: ProfileManager) -> list[ExamProfileOut]:
    return _profiles_out(db)


@router.post("/admin/exam-profiles", response_model=list[ExamProfileOut], status_code=201, summary="New exam profile")
def create_exam_profile(db: DB, who: ProfileManager, body: ExamProfileIn) -> list[ExamProfileOut]:
    from portal_api.modules.assessment import profiles

    profiles.create_profile(db, who, body.code, body.name, body.eligibility_note)
    return _profiles_out(db)


@router.post(
    "/admin/exam-profiles/{profile_id}/versions",
    response_model=ProfileVersionOut,
    status_code=201,
    summary="Start a new draft version (duration, marking, correction policy, sections; source and year)",
)
def new_profile_version(
    db: DB, who: ProfileManager, profile_id: uuid.UUID, body: ProfileVersionIn
) -> ProfileVersionOut:
    from portal_api.modules.assessment import profiles

    return _pv(profiles.save_draft(db, who, profile_id, body.year, body.rules))


@router.put(
    "/admin/exam-profiles/{profile_id}/versions/{version_id}",
    response_model=ProfileVersionOut,
    summary="Edit a draft (clears its verifications)",
)
def edit_profile_version(
    db: DB, who: ProfileManager, profile_id: uuid.UUID, version_id: uuid.UUID, body: ProfileVersionIn
) -> ProfileVersionOut:
    from portal_api.modules.assessment import profiles

    return _pv(profiles.save_draft(db, who, profile_id, body.year, body.rules, version_id))


@router.post(
    "/admin/exam-profile-versions/{version_id}/verify",
    response_model=ProfileVersionOut,
    summary="Record one of two independent verifications (not the author)",
)
def verify_profile_version(db: DB, who: ProfileManager, version_id: uuid.UUID, body: VerifyIn) -> ProfileVersionOut:
    from portal_api.modules.assessment import profiles

    return _pv(profiles.verify(db, who, version_id, body.note))


@router.post(
    "/admin/exam-profile-versions/{version_id}/publish",
    response_model=ProfileVersionOut,
    summary="Publish a verified version; the previous one is retired for new mocks only",
)
def publish_profile_version(db: DB, who: ProfileManager, version_id: uuid.UUID) -> ProfileVersionOut:
    from portal_api.modules.assessment import profiles

    return _pv(profiles.publish(db, who, version_id))


@router.get("/exam-profiles", response_model=list[PublishedProfileOut], summary="Published official test patterns")
def published_exam_profiles(db: DB, who: CurrentPrincipal) -> list[PublishedProfileOut]:
    from portal_api.modules.assessment import profiles

    return [
        PublishedProfileOut(
            code=p.code,
            name=p.name,
            eligibility_note=p.eligibility_note,
            version=v.version,
            year=v.year,
            duration_minutes=v.rules["duration_minutes"],
            total_questions=profiles.total_questions(v.rules),
            sections=v.rules["sections"],
            source_url=v.rules["source_url"],
        )
        for p, v in profiles.published(db)
    ]


# ------------------------------------------------------------------ mocks from published profiles (P09.S2/S3, MOCK-01)
class MockIn(BaseModel):
    code: str = Field(min_length=2, max_length=40)


class MockReadinessOut(BaseModel):
    code: str
    version: int
    sections: list[dict[str, Any]]
    ready: bool
    scheduled: bool


@router.get(
    "/mocks/{code}/readiness",
    response_model=MockReadinessOut,
    summary="Whether every section of a published test pattern has enough approved questions (counts only)",
)
def mock_readiness(db: DB, who: CurrentPrincipal, code: str) -> MockReadinessOut:
    from portal_api.modules.assessment import mocks

    return MockReadinessOut(**mocks.readiness(db, code))


@router.post(
    "/mocks",
    response_model=FormOut,
    status_code=201,
    summary="Build and freeze a mock from the current published version of a test pattern",
    dependencies=[Depends(operations.requires("new_practice_tests"))],
)
def create_mock(
    db: DB,
    who: CurrentPrincipal,
    body: MockIn,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=80)],
) -> FormOut:
    from portal_api.modules.assessment import mocks

    _private(response)
    return _form_out(mocks.build(db, who, body.code, idempotency_key))


# ------------------------------------------------------------------ scheduled mock sessions (P09.S2.T3, SCHEDULE-01)
class MockSessionIn(BaseModel):
    profile_code: str = Field(min_length=2, max_length=40)
    title: str = Field(min_length=3, max_length=200)
    starts_at: datetime
    entry_closes_at: datetime
    window_closes_at: datetime
    results_at: datetime
    late_entry: Literal["fixed_end", "full_duration"] = "fixed_end"
    timezone: str = Field(default="Asia/Karachi", max_length=60)


class AccommodationIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    extra_minutes: int = Field(ge=1, le=240)
    reason: str = Field(min_length=10, max_length=1000)


class CancelIn(BaseModel):
    reason: str = Field(min_length=10, max_length=1000)


class MockSessionOut(BaseModel):
    id: uuid.UUID
    title: str
    profile_code: str
    profile_name: str
    profile_version: int
    timezone: str
    starts_at: datetime
    entry_closes_at: datetime
    window_closes_at: datetime
    results_at: datetime
    late_entry: Literal["fixed_end", "full_duration"]
    duration_minutes: int
    total_questions: int
    state: Literal["upcoming", "open", "entry_closed"]


def _sessions_out(db: Session) -> list[MockSessionOut]:
    from portal_api.modules.assessment import profiles, sessions

    now = db.execute(select(func.now())).scalar_one()
    out = []
    for s, p, v in sessions.upcoming(db):
        state = "upcoming" if now < s.starts_at else "open" if now <= s.entry_closes_at else "entry_closed"
        out.append(
            MockSessionOut(
                id=s.id,
                title=s.title,
                profile_code=p.code,
                profile_name=p.name,
                profile_version=v.version,
                timezone=s.timezone,
                starts_at=s.starts_at,
                entry_closes_at=s.entry_closes_at,
                window_closes_at=s.window_closes_at,
                results_at=s.results_at,
                late_entry=s.late_entry,  # type: ignore[arg-type]
                duration_minutes=int(v.rules["duration_minutes"]),
                total_questions=profiles.total_questions(v.rules),
                state=state,  # type: ignore[arg-type]
            )
        )
    return out


@router.post(
    "/admin/mock-sessions",
    response_model=list[MockSessionOut],
    status_code=201,
    summary="Schedule a mock window for the current published version of a test pattern",
)
def schedule_mock(db: DB, who: ProfileManager, body: MockSessionIn) -> list[MockSessionOut]:
    from portal_api.modules.assessment import sessions

    sessions.schedule(
        db,
        who,
        profile_code=body.profile_code,
        title=body.title,
        starts_at=body.starts_at,
        entry_closes_at=body.entry_closes_at,
        window_closes_at=body.window_closes_at,
        results_at=body.results_at,
        late_entry=body.late_entry,
        timezone=body.timezone,
    )
    return _sessions_out(db)


@router.post(
    "/admin/mock-sessions/{session_id}/accommodations",
    status_code=204,
    summary="Give one learner extra minutes for one session (reason required; audited)",
)
def mock_accommodation(db: DB, who: ProfileManager, session_id: uuid.UUID, body: AccommodationIn) -> Response:
    from portal_api.modules.assessment import sessions
    from portal_api.modules.identity.models import AppUser

    user = db.scalar(select(AppUser).where(func.lower(AppUser.email) == body.email.strip().lower()))
    if user is None:
        raise NotFound("No account with that email.")
    sessions.accommodate(db, who, session_id, user.id, body.extra_minutes, body.reason)
    return Response(status_code=204)


@router.post("/admin/mock-sessions/{session_id}/cancel", status_code=204, summary="Cancel a session before it starts")
def cancel_mock_session(db: DB, who: ProfileManager, session_id: uuid.UUID, body: CancelIn) -> Response:
    from portal_api.modules.assessment import sessions

    sessions.cancel(db, who, session_id, body.reason)
    return Response(status_code=204)


@router.get("/mock-sessions", response_model=list[MockSessionOut], summary="Scheduled mocks you can join")
def mock_sessions(db: DB, who: CurrentPrincipal) -> list[MockSessionOut]:
    return _sessions_out(db)


class JoinOut(BaseModel):
    attempt_id: uuid.UUID


@router.post(
    "/mock-sessions/{session_id}/join",
    response_model=JoinOut,
    summary="Join a scheduled mock (once): builds your frozen form and starts the attempt",
    dependencies=[Depends(operations.requires("new_practice_tests"))],
)
def join_mock_session(db: DB, who: CurrentPrincipal, session_id: uuid.UUID, response: Response) -> JoinOut:
    from portal_api.modules.assessment import sessions

    _private(response)
    return JoinOut(attempt_id=sessions.join(db, who, session_id))
