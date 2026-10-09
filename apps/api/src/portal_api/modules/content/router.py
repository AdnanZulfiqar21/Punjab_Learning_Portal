"""Staff content studio API (P06) and the learner read path for published lessons."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from portal_api.db import get_session
from portal_api.errors import Forbidden, NotFound
from portal_api.modules.access import service as access
from portal_api.modules.audit.models import AuditEvent
from portal_api.modules.content import blocks, kinds, workflow
from portal_api.modules.content.models import Availability, ContentItem, ContentVersion, ItemState
from portal_api.modules.content.schemas import (
    AccessTierIn,
    Actions,
    AssignIn,
    ChangeReasonIn,
    DraftIn,
    HistoryEvent,
    ItemCreateIn,
    ItemDetail,
    ItemSummary,
    LessonOut,
    QuarantineIn,
    ReviewIn,
    ReviewOut,
    RightsIn,
    SourceOut,
    SubmitIn,
    ValidateIn,
    ValidationOut,
    VersionOut,
)
from portal_api.modules.curriculum.models import BookEdition, Chapter, SourceDocument, Topic
from portal_api.modules.identity.deps import CurrentPrincipal, OptionalPrincipal, Principal, require
from portal_api.modules.identity.models import AppUser, StaffRoleGrant
from portal_api.modules.identity.permissions import Permission, Role, permissions_for

router = APIRouter(prefix="/v1/studio", tags=["studio"])
public = APIRouter(prefix="/v1", tags=["lessons"])
DB = Annotated[Session, Depends(get_session)]

STUDIO_PERMISSIONS = {Permission.draft_content, Permission.review_content, Permission.publish_content}
CONTENT_ROLES = {Role.content_author, Role.subject_reviewer, Role.academic_adjudicator, Role.publisher}


def studio_member(principal: CurrentPrincipal) -> Principal:
    if not principal.permissions & STUDIO_PERMISSIONS:
        raise Forbidden("The content studio is for staff with a content role.")
    return principal


Member = Annotated[Principal, Depends(studio_member)]
Author = Annotated[Principal, Depends(require(Permission.draft_content))]
Reviewer = Annotated[Principal, Depends(require(Permission.review_content))]
Publisher = Annotated[Principal, Depends(require(Permission.publish_content))]
Quarantiner = Annotated[Principal, Depends(require(Permission.quarantine_content))]
RightsOwner = Annotated[Principal, Depends(require(Permission.confirm_source_rights))]
Adjudicator = Annotated[Principal, Depends(require(Permission.adjudicate))]


# ------------------------------------------------------------------ serialisation
class _Emails:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.cache: dict[str, str | None] = {}

    def __call__(self, user_id: uuid.UUID | str | None) -> str | None:
        if user_id is None:
            return None
        key = str(user_id)
        if key not in self.cache:
            user = self.db.get(AppUser, uuid.UUID(key))
            self.cache[key] = user.email if user else None
        return self.cache[key]


def _version_out(v: ContentVersion, email: _Emails) -> VersionOut:
    return VersionOut(
        id=v.id,
        number=v.number,
        status=v.status,  # type: ignore[arg-type]
        revision=v.revision,
        content_schema_version=v.content_schema_version,
        body=v.body,
        block_types=v.block_types,
        source_refs=v.source_refs,
        change_reason=v.change_reason,
        created_by=email(v.created_by),
        contributors=[e for e in (email(c) for c in v.contributors) if e],
        updated_by=email(v.updated_by),
        updated_at=v.updated_at,
        submitted_at=v.submitted_at,
        approved_by=email(v.approved_by),
        approved_at=v.approved_at,
        published_by=email(v.published_by),
        published_at=v.published_at,
        reviews=[
            ReviewOut(
                reviewer=email(r.reviewer_id),
                decision=r.decision,  # type: ignore[arg-type]
                comment=r.comment,
                checklist=r.checklist or {},
                created_at=r.created_at,
            )
            for r in v.reviews
        ],
    )


def _open_feedback(item: ContentItem) -> int:
    if item.state != ItemState.changes_requested.value or item.working is None:
        return 0
    return sum(1 for r in item.working.reviews if r.decision == "request_changes")


def _summary_fields(
    db: Session,
    item: ContentItem,
    email: _Emails,
    chapters: dict[uuid.UUID, Chapter] | None = None,
    topics: dict[uuid.UUID, Topic] | None = None,
) -> dict[str, object]:
    chapter = chapters.get(item.chapter_id) if chapters is not None else db.get(Chapter, item.chapter_id)
    topic = None
    if item.topic_id:
        topic = topics.get(item.topic_id) if topics is not None else db.get(Topic, item.topic_id)
    return {
        "id": item.id,
        "kind": item.kind,
        "title": item.title,
        "state": item.state,
        "availability": item.availability,
        "grade_number": item.grade_number,
        "subject_code": item.subject_code,
        "chapter_id": item.chapter_id,
        "chapter_title": chapter.title if chapter else "",
        "topic_id": item.topic_id,
        "topic_title": topic.title if topic else None,
        "working_version": item.working.number if item.working else None,
        "published_version": item.published.number if item.published else None,
        "created_by": email(item.created_by),
        "assigned_reviewer": email(item.assigned_reviewer_id),
        "assigned_reviewer_id": item.assigned_reviewer_id,
        "updated_at": item.updated_at,
        "open_feedback": _open_feedback(item),
        "family_id": item.family_id,
        "parent_item_id": item.parent_item_id,
        "quarantine_level": item.quarantine_level,
        "access_tier": item.access_tier,
    }


def _eligible_reviewers(db: Session, item: ContentItem) -> int:
    contributors = set(item.working.contributors) if item.working else set()
    users = db.scalars(
        select(StaffRoleGrant.user_id).where(
            StaffRoleGrant.revoked_at.is_(None),
            StaffRoleGrant.role.in_([Role.subject_reviewer.value, Role.academic_adjudicator.value]),
        )
    ).all()
    return sum(
        1
        for uid in set(users)
        if str(uid) not in contributors
        and Permission.review_content
        in permissions_for(workflow.roles_in_scope(db, uid, item.grade_number, item.subject_code))
    )


def _detail(db: Session, item: ContentItem, who: Principal) -> ItemDetail:
    email = _Emails(db)
    chapter = db.get(Chapter, item.chapter_id)
    assert chapter is not None
    book = db.get(BookEdition, chapter.book_id)
    assert book is not None
    doc = db.get(SourceDocument, book.source_document_id)
    assert doc is not None
    perms = permissions_for(workflow.roles_in_scope(db, who.user.id, item.grade_number, item.subject_code))
    mfa = who.claims.mfa
    retired = item.availability == Availability.retired.value
    me = str(who.user.id)
    contributor = item.working is not None and me in item.working.contributors
    editable = item.state in (ItemState.draft.value, ItemState.changes_requested.value)
    can_draft = Permission.draft_content in perms and not retired
    can_review = (
        Permission.review_content in perms
        and not retired
        and item.state == ItemState.submitted.value
        and not contributor
    )
    actions = Actions(
        edit=can_draft and editable,
        submit=can_draft and editable,
        withdraw=can_draft and item.state == ItemState.submitted.value,
        review=can_review and item.assigned_reviewer_id in (None, who.user.id),
        claim=can_review and item.assigned_reviewer_id != who.user.id,
        publish=Permission.publish_content in perms
        and mfa
        and not retired
        and item.state == ItemState.approved.value
        and not contributor,
        revise=can_draft and item.state == ItemState.published.value,
        quarantine=Permission.quarantine_content in perms and mfa and item.availability == Availability.live.value,
        release=Permission.quarantine_content in perms and mfa and item.availability == Availability.quarantined.value,
        retire=Permission.publish_content in perms and mfa and not retired,
        set_access_tier=Permission.publish_content in perms
        and mfa
        and not retired
        and kinds.get(item.kind).learner_readable,
        change_quarantine_level=Permission.quarantine_content in perms
        and mfa
        and item.availability == Availability.quarantined.value
        and bool(kinds.get(item.kind).quarantine_levels),
        correct_score=Permission.adjudicate in perms
        and mfa
        and item.kind == "mcq"
        and item.availability == Availability.quarantined.value
        and item.quarantine_level in ("VOID", "KEY_ERROR"),
    )
    blockers: list[str] = []
    if item.working is not None and not retired:
        if item.state == ItemState.submitted.value and _eligible_reviewers(db, item) == 0:
            blockers.append(
                "No independent academic reviewer is assigned to this subject and class yet (BLOCKERS B01). "
                "The item stays private in review."
            )
        if item.state == ItemState.approved.value:
            blockers += workflow.validate_version(db, item, item.working, for_publication=True)["errors"]
        if item.state == ItemState.approved.value and contributor:
            blockers.append("You edited this version, so someone else must publish it.")
    published = item.published if item.published and item.published.id != item.working_version_id else None
    return ItemDetail(
        **_summary_fields(db, item, email),  # type: ignore[arg-type]
        availability_reason=item.availability_reason,
        working=_version_out(item.working, email) if item.working else None,
        published=_version_out(published, email) if published else None,
        source=_source_out(doc),
        chapter_pdf_start=chapter.pdf_start,
        chapter_pdf_end=chapter.pdf_end,
        actions=actions,
        blockers=blockers,
        review_checklist=list(kinds.get(item.kind).review_checklist),
        quarantine_levels=list(kinds.get(item.kind).quarantine_levels),
    )


def _source_out(doc: SourceDocument) -> SourceOut:
    return SourceOut(
        id=doc.id,
        source_id=doc.source_id,
        title=doc.title,
        grade_number=doc.grade_number,
        subject_code=doc.subject_code,
        pdf_pages=doc.pdf_pages,
        missing_pages=doc.missing_pages or [],
        publication_rights=doc.publication_rights,  # type: ignore[arg-type]
        publication_rights_evidence=doc.publication_rights_evidence,
        publication_rights_set_at=doc.publication_rights_set_at,
    )


def _no_store(response: Response) -> None:
    # Drafts and reviews are private staff data; never cache them in shared caches (§5.3).
    response.headers["Cache-Control"] = "private, no-store"


# ------------------------------------------------------------------ studio: reading
@router.get("/block-registry", summary="Block types, schema version and renderer requirements (§5.4)")
def block_registry(_: Member) -> dict[str, object]:
    return blocks.registry_document()


@router.get("/queue", response_model=list[ItemSummary], summary="Editorial work queue (P06.S1.T2)")
def queue(
    db: DB,
    who: Member,
    response: Response,
    state: Annotated[str | None, Query(pattern="^(draft|submitted|changes_requested|approved|published)$")] = None,
    availability: Annotated[str | None, Query(pattern="^(unpublished|live|quarantined|retired)$")] = None,
    grade: Annotated[int | None, Query(ge=11, le=12)] = None,
    kind: Annotated[str | None, Query(pattern="^(lesson|mcq|written|rubric)$")] = None,
    subject: Annotated[str | None, Query(max_length=40)] = None,
    mine: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[ItemSummary]:
    _no_store(response)
    # Scope is applied in SQL before LIMIT, and related rows are batch-loaded (no per-item queries).
    stmt = (
        select(ContentItem)
        .where(workflow.scope_clause(db, who.user.id, CONTENT_ROLES))
        .options(
            selectinload(ContentItem.working).selectinload(ContentVersion.reviews),
            selectinload(ContentItem.published),
        )
        .order_by(ContentItem.updated_at.desc())
        .limit(limit)
    )
    if state:
        stmt = stmt.where(ContentItem.state == state)
    if availability:
        stmt = stmt.where(ContentItem.availability == availability)
    else:
        stmt = stmt.where(ContentItem.availability != Availability.retired.value)
    if grade:
        stmt = stmt.where(ContentItem.grade_number == grade)
    if kind:
        stmt = stmt.where(ContentItem.kind == kind)
    if subject:
        stmt = stmt.where(ContentItem.subject_code == subject)
    if mine:
        stmt = stmt.where((ContentItem.created_by == who.user.id) | (ContentItem.assigned_reviewer_id == who.user.id))
    items = list(db.scalars(stmt))
    chapters = {c.id: c for c in db.scalars(select(Chapter).where(Chapter.id.in_({i.chapter_id for i in items})))}
    topic_ids = {i.topic_id for i in items if i.topic_id}
    topics = {t.id: t for t in db.scalars(select(Topic).where(Topic.id.in_(topic_ids)))} if topic_ids else {}
    email = _Emails(db)
    return [ItemSummary(**_summary_fields(db, i, email, chapters, topics)) for i in items]  # type: ignore[arg-type]


def _scoped_item(db: Session, who: Principal, item_id: uuid.UUID) -> ContentItem:
    item = workflow.get_item(db, item_id)
    if not workflow.roles_in_scope(db, who.user.id, item.grade_number, item.subject_code) & CONTENT_ROLES:
        raise NotFound("Content item not found.")  # don't reveal items outside the caller's scope
    return item


@router.get("/items/{item_id}", response_model=ItemDetail)
def item_detail(db: DB, who: Member, item_id: uuid.UUID, response: Response) -> ItemDetail:
    _no_store(response)
    return _detail(db, _scoped_item(db, who, item_id), who)


@router.get("/items/{item_id}/history", response_model=list[HistoryEvent], summary="Audit history for one item")
def item_history(db: DB, who: Member, item_id: uuid.UUID, response: Response) -> list[HistoryEvent]:
    _no_store(response)
    _scoped_item(db, who, item_id)
    email = _Emails(db)
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.target_type == "content_item", AuditEvent.target_id == str(item_id))
        .order_by(AuditEvent.at, AuditEvent.id)
    )
    return [HistoryEvent(at=e.at, action=e.action, actor=email(e.actor_user_id), details=e.details) for e in events]


@router.get("/sources", response_model=list[SourceOut], summary="Source documents and their publication-rights state")
def sources(db: DB, _: Member, response: Response) -> list[SourceOut]:
    _no_store(response)
    return [_source_out(d) for d in db.scalars(select(SourceDocument).order_by(SourceDocument.source_id))]


@router.post("/validate", response_model=ValidationOut, summary="Dry-run validation for the editor (writes nothing)")
def validate(db: DB, _: Member, body: ValidateIn) -> ValidationOut:
    return ValidationOut(
        **workflow.validate_draft(
            db, body.chapter_id, body.body, body.source_refs, body.for_publication, kind=body.kind
        )
    )


# ------------------------------------------------------------------ studio: transitions
@router.post("/items", response_model=ItemDetail, status_code=201)
def create(db: DB, who: Author, body: ItemCreateIn) -> ItemDetail:
    item = workflow.create_item(
        db,
        who,
        chapter_id=body.chapter_id,
        topic_id=body.topic_id,
        title=body.title,
        kind=body.kind,
        family_of=body.family_of,
        parent_item_id=body.parent_item_id,
    )
    return _detail(db, item, who)


@router.put("/items/{item_id}/draft", response_model=ItemDetail, summary="Autosave with a revision check (P06.S1.T3)")
def save_draft(db: DB, who: Author, item_id: uuid.UUID, body: DraftIn) -> ItemDetail:
    item = workflow.save_draft(
        db, who, item_id, revision=body.revision, title=body.title, body=body.body, source_refs=body.source_refs
    )
    return _detail(db, item, who)


@router.post("/items/{item_id}/submit", response_model=ItemDetail)
def submit(db: DB, who: Author, item_id: uuid.UUID, body: SubmitIn) -> ItemDetail:
    return _detail(db, workflow.submit(db, who, item_id, body.note), who)


@router.post("/items/{item_id}/withdraw", response_model=ItemDetail)
def withdraw(db: DB, who: Author, item_id: uuid.UUID) -> ItemDetail:
    return _detail(db, workflow.withdraw(db, who, item_id), who)


@router.post("/items/{item_id}/assign", response_model=ItemDetail)
def assign(db: DB, who: Member, item_id: uuid.UUID, body: AssignIn) -> ItemDetail:
    return _detail(db, workflow.assign_reviewer(db, who, item_id, body.reviewer_id), who)


@router.post("/items/{item_id}/review", response_model=ItemDetail)
def review(db: DB, who: Reviewer, item_id: uuid.UUID, body: ReviewIn) -> ItemDetail:
    item = workflow.review(db, who, item_id, decision=body.decision, comment=body.comment, checklist=body.checklist)
    return _detail(db, item, who)


@router.post("/items/{item_id}/publish", response_model=ItemDetail)
def publish(db: DB, who: Publisher, item_id: uuid.UUID) -> ItemDetail:
    return _detail(db, workflow.publish(db, who, item_id), who)


@router.post("/items/{item_id}/revise", response_model=ItemDetail)
def revise(db: DB, who: Author, item_id: uuid.UUID, body: ChangeReasonIn) -> ItemDetail:
    return _detail(db, workflow.revise(db, who, item_id, body.reason), who)


@router.post("/items/{item_id}/quarantine", response_model=ItemDetail)
def quarantine(db: DB, who: Quarantiner, item_id: uuid.UUID, body: QuarantineIn) -> ItemDetail:
    return _detail(db, workflow.quarantine(db, who, item_id, body.reason, body.level), who)


@router.post(
    "/items/{item_id}/access-tier",
    response_model=ItemDetail,
    summary="Mark a lesson as a free preview or premium (publishers, MFA, audited with a reason)",
)
def access_tier(db: DB, who: Publisher, item_id: uuid.UUID, body: AccessTierIn) -> ItemDetail:
    return _detail(db, workflow.set_access_tier(db, who, item_id, body.tier, body.reason), who)


@router.post("/items/{item_id}/release", response_model=ItemDetail)
def release(db: DB, who: Quarantiner, item_id: uuid.UUID, body: ChangeReasonIn) -> ItemDetail:
    return _detail(db, workflow.release(db, who, item_id, body.reason), who)


@router.post("/items/{item_id}/retire", response_model=ItemDetail)
def retire(db: DB, who: Publisher, item_id: uuid.UUID, body: ChangeReasonIn) -> ItemDetail:
    return _detail(db, workflow.retire(db, who, item_id, body.reason), who)


@router.put(
    "/sources/{source_id}/publication-rights",
    response_model=SourceOut,
    summary="Owner's publication-rights decision for material derived from a source (audited, MFA)",
)
def set_rights(db: DB, who: RightsOwner, source_id: uuid.UUID, body: RightsIn) -> SourceOut:
    return _source_out(workflow.set_publication_rights(db, who, source_id, rights=body.rights, evidence=body.evidence))


# ------------------------------------------------------------------ learners
@public.get(
    "/chapters/{chapter_id}/lessons",
    response_model=list[LessonOut],
    summary="Published, live lessons for a chapter (academically approved; never drafts)",
)
def chapter_lessons(db: DB, who: OptionalPrincipal, chapter_id: uuid.UUID, response: Response) -> list[LessonOut]:
    """Every live lesson is listed. Premium bodies go only to callers with an active plan or trial (review R07);
    others see the title marked locked. Free previews are readable by everyone."""
    chapter = db.get(Chapter, chapter_id)
    if chapter is None or chapter.retired_at is not None:
        raise NotFound("Chapter not found.")
    entitled = (
        who is not None
        and bool(access.active_entitlements(db, who.user.id, access.db_now(db)))
        and access.device_gate(db, who.user.id) is None  # trial use on a native device needs its authorization
    )
    if who is None:
        # The anonymous response holds preview bodies only, identical for every anonymous caller: safe to share.
        response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=300"
    else:
        response.headers["Cache-Control"] = "private, no-store"  # personalised: never stored by shared caches
    response.headers["Vary"] = "Authorization"
    rows = db.execute(
        select(ContentItem, ContentVersion)
        .join(ContentVersion, ContentVersion.id == ContentItem.published_version_id)
        .where(
            ContentItem.chapter_id == chapter_id,
            ContentItem.availability == Availability.live.value,
            # Key isolation (P08.S2.T3): questions are never served here, even when published.
            ContentItem.kind.in_([k.name for k in kinds.KINDS.values() if k.learner_readable]),
        )
        .order_by(ContentVersion.published_at, ContentItem.id)
    ).all()
    out = []
    for i, v in rows:
        locked = i.access_tier != "preview" and not entitled
        out.append(
            LessonOut(
                id=i.id,
                title=i.title,
                topic_id=i.topic_id,
                version=v.number,
                published_at=v.published_at or v.updated_at,  # always set for published versions
                access_tier=i.access_tier,  # type: ignore[arg-type]
                locked=locked,
                content_schema_version=v.content_schema_version,
                block_types=[] if locked else v.block_types,
                body=None if locked else v.body,
                source_refs=v.source_refs,  # textbook page references are not premium content
            )
        )
    return out


# ------------------------------------------------------------------ MCQ score corrections (§5.7, P10.S3.T4)
class ScoreCorrectionIn(BaseModel):
    defect: Literal["VOID", "KEY_ERROR"]
    corrected_option_id: str | None = Field(default=None, max_length=80, description="KEY_ERROR only")
    reason: str = Field(min_length=10, max_length=2000)


class ScoreCorrectionOut(BaseModel):
    id: uuid.UUID
    version_id: uuid.UUID
    defect: Literal["VOID", "KEY_ERROR"]
    corrected_option_id: str | None
    reason: str
    decided_at: datetime
    status: Literal["effective", "superseded"]
    supersedes_id: uuid.UUID | None
    affected_attempts: int
    rescored: int = Field(default=0, description="Attempts given a new score version by this request")


def _correction_out(db: Session, a: Any, rescored: int = 0) -> ScoreCorrectionOut:
    from portal_api.modules.assessment import adjudications

    return ScoreCorrectionOut(
        id=a.id,
        version_id=a.version_id,
        defect=a.defect,
        corrected_option_id=a.corrected_option_id,
        reason=a.reason,
        decided_at=a.decided_at,
        status=a.status,
        supersedes_id=a.supersedes_id,
        affected_attempts=len(adjudications.affected_attempts(db, a.version_id)),
        rescored=rescored,
    )


@router.post(
    "/items/{item_id}/score-corrections",
    response_model=ScoreCorrectionOut,
    status_code=201,
    summary="Record a reviewed VOID or KEY_ERROR correction and re-score affected attempts (adjudicators, MFA)",
)
def record_score_correction(
    db: DB, who: Adjudicator, item_id: uuid.UUID, body: ScoreCorrectionIn
) -> ScoreCorrectionOut:
    from portal_api.modules.assessment import adjudications

    a = adjudications.record_adjudication(
        db, who, item_id, defect=body.defect, reason=body.reason, corrected_option_id=body.corrected_option_id
    )
    rescored = adjudications.propagate(db, a.version_id)
    return _correction_out(db, a, rescored)


@router.get(
    "/items/{item_id}/score-corrections",
    response_model=list[ScoreCorrectionOut],
    summary="Score corrections recorded for a question",
)
def list_score_corrections(db: DB, who: Member, item_id: uuid.UUID) -> list[ScoreCorrectionOut]:
    from portal_api.modules.assessment import adjudications

    workflow.get_item(db, item_id)
    return [_correction_out(db, a) for a in adjudications.corrections(db, item_id)]
