"""Inclusion records, mapping review and coverage (roadmap P05.S2.T1-T3; INCLUSION-01).

An **inclusion record** says, for one published concept (CONCEPTS-01) in one **mapping**, whether it is `included`,
`excluded`, `not_applicable` or `unverified`, why, from which source, and which version of that source. The mappings
are independent: the full curriculum, the (possibly reduced) board syllabus, and the MDCAT and ECAT entrance syllabi.
Board and entrance mappings are per year; the full curriculum is not. One record per concept, mapping and year.

**Review:** a record is drafted by a content author and published only by an independent subject reviewer (not its
author); it must name its source version. A published record is frozen: a change is a new record for a new year or a
new source version.

**Reports:** concepts no published record in a mapping covers yet (`unmapped`), and contradictions between mappings
(an entrance syllabus including a concept the full curriculum excludes or marks not applicable).

**Coverage:** for each concept in a mapping, whether it is included, and the published content behind it through its
mapped topics: live lessons, live practice question families and academically approved lectures. Content *available*
is never presented as syllabus coverage *claimed*: coverage counts only included, published records. The learner's
syllabus-coverage meter reads these same records once they exist for the learner's mapping.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, SmallInteger, String, Text, func, select, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.db import Base, get_session
from portal_api.errors import Conflict, Forbidden, NotFound, Unprocessable
from portal_api.modules.audit.models import record
from portal_api.modules.content.concepts import Concept, ConceptTopic, _any_grade_roles
from portal_api.modules.content.router import studio_member
from portal_api.modules.identity.deps import Principal

SCOPES = ("full_curriculum", "board_syllabus", "mdcat", "ecat")
STATES = ("included", "excluded", "not_applicable", "unverified")
YEARLY = {"board_syllabus", "mdcat", "ecat"}
Scope = Literal["full_curriculum", "board_syllabus", "mdcat", "ecat"]
State = Literal["included", "excluded", "not_applicable", "unverified"]


class InclusionRecord(Base):
    __tablename__ = "inclusion_record"
    __table_args__ = (
        CheckConstraint(f"scope in ({', '.join(repr(s) for s in SCOPES)})", name="inclusion_scope"),
        CheckConstraint(f"state in ({', '.join(repr(s) for s in STATES)})", name="inclusion_state"),
        CheckConstraint("status in ('draft', 'published')", name="inclusion_status"),
        Index("uq_inclusion_concept_scope_year", "concept_id", "scope", text("coalesce(year, 0)"), unique=True),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("concept.id", ondelete="RESTRICT"), index=True)
    scope: Mapped[str] = mapped_column(String(20))
    year: Mapped[int | None] = mapped_column(SmallInteger)
    state: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    source_version: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(10), default="draft")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    published_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _concept_in_scope(db: Session, who: Principal, concept_id: uuid.UUID) -> Concept:
    c = db.get(Concept, concept_id)
    if c is None or not _any_grade_roles(db, who, c.subject_code):
        raise NotFound("Concept not found.")
    return c


def create(db: Session, who: Principal, body: RecordIn) -> InclusionRecord:
    c = _concept_in_scope(db, who, body.concept_id)
    if "content_author" not in _any_grade_roles(db, who, c.subject_code):
        raise Forbidden("Only a content author in this subject drafts inclusion records.")
    if c.status != "published":
        raise Unprocessable("Map only published concepts; publish the concept first.")
    r = InclusionRecord(
        concept_id=c.id,
        scope=body.scope,
        year=body.year,
        state=body.state,
        reason=body.reason,
        source=body.source,
        source_version=body.source_version,
        created_by=who.user.id,
    )
    db.add(r)
    try:
        db.flush()
    except IntegrityError as e:
        db.rollback()
        raise Conflict(
            "This concept already has a record in this mapping and year.", code_reason="RECORD_EXISTS"
        ) from e
    record(db, actor=who.user.id, action="inclusion.drafted", target_type="inclusion_record", target_id=str(r.id),
           details={"concept": str(c.id), "scope": r.scope, "year": r.year, "state": r.state})  # fmt: skip
    db.commit()
    return r


def _get(db: Session, who: Principal, record_id: uuid.UUID, *, lock: bool = False) -> tuple[InclusionRecord, Concept]:
    stmt = select(InclusionRecord).where(InclusionRecord.id == record_id)
    r = db.scalar(stmt.with_for_update() if lock else stmt)
    if r is None:
        raise NotFound("Record not found.")
    return r, _concept_in_scope(db, who, r.concept_id)


def update(db: Session, who: Principal, record_id: uuid.UUID, body: RecordPatch) -> InclusionRecord:
    r, c = _get(db, who, record_id, lock=True)
    if "content_author" not in _any_grade_roles(db, who, c.subject_code):
        raise Forbidden("Only a content author in this subject edits inclusion records.")
    if r.status != "draft":
        raise Conflict("A published record is frozen. Record a new year or source version instead.")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(r, k, v)
    if not r.source_version.strip():
        raise Unprocessable("Name the version of the source.")
    db.commit()
    return r


def publish(db: Session, who: Principal, record_id: uuid.UUID) -> InclusionRecord:
    r, c = _get(db, who, record_id, lock=True)
    if "subject_reviewer" not in _any_grade_roles(db, who, c.subject_code):
        raise Forbidden("Only a subject reviewer in this subject publishes inclusion records.")
    if r.created_by == who.user.id:
        raise Forbidden("A record is published by an independent reviewer, not its author.")
    if r.status != "draft":
        raise Conflict("This record is already published.")
    r.status, r.published_by, r.published_at = "published", who.user.id, func.now()
    details = {"scope": r.scope, "year": r.year, "state": r.state, "source_version": r.source_version}
    record(db, actor=who.user.id, action="inclusion.published", target_type="inclusion_record", target_id=str(r.id),
           details=details)  # fmt: skip
    db.commit()
    return r


def listing(
    db: Session, who: Principal, scope: str | None, year: int | None, subject: str | None
) -> list[tuple[InclusionRecord, Concept]]:
    stmt = select(InclusionRecord, Concept).join(Concept, Concept.id == InclusionRecord.concept_id)
    if scope:
        stmt = stmt.where(InclusionRecord.scope == scope)
    if year:
        stmt = stmt.where(InclusionRecord.year == year)
    if subject:
        stmt = stmt.where(Concept.subject_code == subject)
    rows = db.execute(stmt.order_by(Concept.code, InclusionRecord.scope).limit(1000)).all()
    return [(r, c) for r, c in rows if _any_grade_roles(db, who, c.subject_code)]


def _published(db: Session, subject: str) -> list[Concept]:
    return list(
        db.scalars(
            select(Concept).where(Concept.subject_code == subject, Concept.status == "published").order_by(Concept.code)
        )
    )


def report(db: Session, who: Principal, subject: str, scope: str, year: int | None) -> dict[str, Any]:
    if not _any_grade_roles(db, who, subject):
        raise NotFound("No concepts in your subjects here.")
    concepts = _published(db, subject)
    ids = [c.id for c in concepts]
    recs = list(
        db.scalars(
            select(InclusionRecord).where(InclusionRecord.concept_id.in_(ids), InclusionRecord.status == "published")
        )
    ) if ids else []  # fmt: skip
    in_scope = {r.concept_id for r in recs if r.scope == scope and (r.year == year if scope in YEARLY else True)}
    by_concept: dict[uuid.UUID, list[InclusionRecord]] = {}
    for r in recs:
        by_concept.setdefault(r.concept_id, []).append(r)
    contradictions = []
    for c in concepts:
        rs = by_concept.get(c.id, [])
        full = next((r for r in rs if r.scope == "full_curriculum"), None)
        if full is None or full.state not in ("excluded", "not_applicable"):
            continue
        for r in rs:
            if r.scope in ("mdcat", "ecat", "board_syllabus") and r.state == "included":
                contradictions.append(
                    {
                        "concept_id": c.id,
                        "code": c.code,
                        "detail": " ".join(f"{r.scope} {r.year or ''}".split())
                        + f": included, but the full curriculum says {full.state}.",
                    }
                )
    return {
        "subject": subject,
        "scope": scope,
        "year": year,
        "unmapped": [{"concept_id": c.id, "code": c.code, "title": c.title} for c in concepts if c.id not in in_scope],
        "contradictions": contradictions,
    }


def coverage(db: Session, who: Principal, subject: str, scope: str, year: int | None) -> dict[str, Any]:
    from portal_api.modules.content.lectures import Lecture
    from portal_api.modules.content.models import Availability, ContentItem
    from portal_api.modules.curriculum.models import Topic

    if not _any_grade_roles(db, who, subject):
        raise NotFound("No concepts in your subjects here.")
    concepts = _published(db, subject)
    states = {
        r.concept_id: r.state
        for r in db.scalars(
            select(InclusionRecord).where(
                InclusionRecord.scope == scope,
                InclusionRecord.status == "published",
                InclusionRecord.year == year if scope in YEARLY else InclusionRecord.year.is_(None),
            )
        )
    }
    live = ContentItem.availability == Availability.live.value
    rows = []
    for c in concepts:
        topic_ids = list(db.scalars(select(ConceptTopic.topic_id).where(ConceptTopic.concept_id == c.id)))
        chapter_ids = list(db.scalars(select(Topic.chapter_id).where(Topic.id.in_(topic_ids)))) if topic_ids else []
        lessons = questions = lectures = 0
        if topic_ids:
            lessons = int(
                db.scalar(
                    select(func.count()).where(ContentItem.kind == "lesson", live, ContentItem.topic_id.in_(topic_ids))
                )
                or 0
            )
            questions = int(
                db.scalar(
                    select(func.count(func.distinct(func.coalesce(ContentItem.family_id, ContentItem.id)))).where(
                        ContentItem.kind == "mcq", live, ContentItem.topic_id.in_(topic_ids)
                    )
                )
                or 0
            )
        if chapter_ids:
            lectures = int(
                db.scalar(select(func.count()).where(Lecture.chapter_id.in_(chapter_ids), Lecture.status == "approved"))
                or 0
            )
        rows.append(
            {
                "concept_id": c.id,
                "code": c.code,
                "title": c.title,
                "state": states.get(c.id),
                "included": states.get(c.id) == "included",
                "live_lessons": lessons,
                "live_questions": questions,
                "approved_lectures": lectures,
            }
        )
    included = [r for r in rows if r["included"]]
    return {
        "subject": subject,
        "scope": scope,
        "year": year,
        "included": len(included),
        "with_lessons": sum(1 for r in included if r["live_lessons"]),
        "with_questions": sum(1 for r in included if r["live_questions"]),
        "with_lectures": sum(1 for r in included if r["approved_lectures"]),
        "concepts": rows,
    }


# ------------------------------------------------------------------ routes
router = APIRouter(prefix="/v1/studio", tags=["studio"])
DB = Annotated[Session, Depends(get_session)]
Member = Annotated[Principal, Depends(studio_member)]


class RecordIn(BaseModel):
    concept_id: uuid.UUID
    scope: Scope
    year: int | None = Field(default=None, ge=2020, le=2100)
    state: State
    reason: str = Field(min_length=3, max_length=2000)
    source: str = Field(min_length=3, max_length=500, description="The syllabus or notice, with section or page")
    source_version: str = Field(min_length=1, max_length=120, description="e.g. the notice date or document version")

    @model_validator(mode="after")
    def _year_rule(self) -> RecordIn:
        if self.scope in YEARLY and self.year is None:
            raise ValueError("Board and entrance mappings name their year.")
        if self.scope == "full_curriculum" and self.year is not None:
            raise ValueError("The full curriculum mapping isn't per year.")
        return self


class RecordPatch(BaseModel):
    state: State | None = None
    reason: str | None = Field(default=None, min_length=3, max_length=2000)
    source: str | None = Field(default=None, min_length=3, max_length=500)
    source_version: str | None = Field(default=None, max_length=120)


class RecordOut(BaseModel):
    id: uuid.UUID
    concept_id: uuid.UUID
    concept_code: str
    concept_title: str
    scope: Scope
    year: int | None
    state: State
    reason: str
    source: str
    source_version: str
    status: Literal["draft", "published"]
    published_at: datetime | None


class ReportRow(BaseModel):
    concept_id: uuid.UUID
    code: str
    title: str | None = None
    detail: str | None = None


class ReportOut(BaseModel):
    subject: str
    scope: Scope
    year: int | None
    unmapped: list[ReportRow]
    contradictions: list[ReportRow]


class CoverageRow(BaseModel):
    concept_id: uuid.UUID
    code: str
    title: str
    state: State | None
    included: bool
    live_lessons: int
    live_questions: int
    approved_lectures: int


class CoverageOut(BaseModel):
    subject: str
    scope: Scope
    year: int | None
    included: int
    with_lessons: int
    with_questions: int
    with_lectures: int
    concepts: list[CoverageRow]


def _out(r: InclusionRecord, c: Concept) -> RecordOut:
    return RecordOut(
        id=r.id,
        concept_id=c.id,
        concept_code=c.code,
        concept_title=c.title,
        scope=r.scope,  # type: ignore[arg-type]
        year=r.year,
        state=r.state,  # type: ignore[arg-type]
        reason=r.reason,
        source=r.source,
        source_version=r.source_version,
        status=r.status,  # type: ignore[arg-type]
        published_at=r.published_at,
    )


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


def _year(scope: str, year: int | None) -> int | None:
    if scope in YEARLY and year is None:
        raise Unprocessable("Board and entrance mappings name their year.")
    return year if scope in YEARLY else None


@router.get("/inclusion", response_model=list[RecordOut], summary="Inclusion records in your subjects")
def list_records(
    db: DB,
    who: Member,
    response: Response,
    scope: Scope | None = None,
    year: Annotated[int | None, Query(ge=2020, le=2100)] = None,
    subject: Annotated[str | None, Query(max_length=40)] = None,
) -> list[RecordOut]:
    _private(response)
    return [_out(r, c) for r, c in listing(db, who, scope, year, subject)]


@router.post("/inclusion", response_model=RecordOut, status_code=201, summary="Draft an inclusion record")
def create_record(db: DB, who: Member, body: RecordIn, response: Response) -> RecordOut:
    _private(response)
    r = create(db, who, body)
    c = db.get(Concept, r.concept_id)
    assert c is not None
    return _out(r, c)


@router.put("/inclusion/{record_id}", response_model=RecordOut, summary="Edit a draft inclusion record")
def edit_record(db: DB, who: Member, record_id: uuid.UUID, body: RecordPatch, response: Response) -> RecordOut:
    _private(response)
    r = update(db, who, record_id, body)
    c = db.get(Concept, r.concept_id)
    assert c is not None
    return _out(r, c)


@router.post(
    "/inclusion/{record_id}/publish", response_model=RecordOut, summary="Publish (an independent subject reviewer)"
)
def publish_record(db: DB, who: Member, record_id: uuid.UUID, response: Response) -> RecordOut:
    _private(response)
    r = publish(db, who, record_id)
    c = db.get(Concept, r.concept_id)
    assert c is not None
    return _out(r, c)


@router.get("/inclusion/report", response_model=ReportOut, summary="Unmapped concepts and contradictory mappings")
def inclusion_report(
    db: DB,
    who: Member,
    response: Response,
    subject: Annotated[str, Query(min_length=2, max_length=40)],
    scope: Scope,
    year: Annotated[int | None, Query(ge=2020, le=2100)] = None,
) -> ReportOut:
    _private(response)
    return ReportOut(**report(db, who, subject, scope, _year(scope, year)))


@router.get("/inclusion/coverage", response_model=CoverageOut, summary="Published content behind each mapped concept")
def inclusion_coverage(
    db: DB,
    who: Member,
    response: Response,
    subject: Annotated[str, Query(min_length=2, max_length=40)],
    scope: Scope,
    year: Annotated[int | None, Query(ge=2020, le=2100)] = None,
) -> CoverageOut:
    _private(response)
    return CoverageOut(**coverage(db, who, subject, scope, _year(scope, year)))
