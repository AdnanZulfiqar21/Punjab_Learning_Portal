"""Learning concepts (outcomes) and prerequisites (roadmap P05.S1.T2; CONCEPTS-01).

A **concept** is a canonical learning outcome: written once (stable `code`, title, outcome statement, subject) and
**mapped** to the topics that teach it in any edition or course, so a concept taught in Class 11 and revisited in Class
12 is one record with two mappings, never a duplicate. Mapping a topic needs a content role in that topic's class and
subject, and only topics of the concept's subject can be mapped.

**Prerequisites** are edges "concept A needs concept B". The graph stays acyclic (an edge that would close a cycle is
refused with `PREREQUISITE_CYCLE`). An edge may name an introductory **bridging lesson**, a live lesson of the same
subject that covers the prerequisite for learners who haven't met it.

Concepts are academic content written by staff, never generated here. A draft is published only by an independent
reviewer (not its author) once it cites source pages and maps at least one topic. A published concept is frozen; change
means a new concept and retiring the old one. Inclusion of a concept in a syllabus or exam (P05.S2) is recorded
separately.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.db import Base, get_session
from portal_api.errors import Conflict, Forbidden, NotFound, Unprocessable
from portal_api.modules.audit.models import record
from portal_api.modules.content.router import studio_member
from portal_api.modules.identity.deps import Principal

CODE = r"^[a-z0-9][a-z0-9.\-]{2,79}$"
STATUSES = ("draft", "published", "retired")


class Concept(Base):
    __tablename__ = "concept"
    __table_args__ = (CheckConstraint(f"status in ({', '.join(repr(s) for s in STATUSES)})", name="concept_status"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(80), unique=True)
    subject_code: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(Text)
    statement: Mapped[str] = mapped_column(Text)
    source_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(10), default="draft")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    published_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConceptTopic(Base):
    __tablename__ = "concept_topic"
    __table_args__ = (UniqueConstraint("concept_id", "topic_id", name="uq_concept_topic"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("concept.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topic.id", ondelete="RESTRICT"), index=True)


class ConceptPrerequisite(Base):
    __tablename__ = "concept_prerequisite"
    __table_args__ = (
        UniqueConstraint("concept_id", "requires_id", name="uq_concept_prerequisite"),
        CheckConstraint("concept_id <> requires_id", name="concept_prerequisite_not_self"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("concept.id", ondelete="CASCADE"), index=True)
    requires_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("concept.id", ondelete="RESTRICT"), index=True)
    bridging_lesson_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("content_item.id", ondelete="RESTRICT"))


# ------------------------------------------------------------------ rules
def _roles(db: Session, who: Principal, grade: int, subject: str) -> set[str]:
    from portal_api.modules.content.workflow import roles_in_scope

    return set(roles_in_scope(db, who.user.id, grade, subject))


def _any_grade_roles(db: Session, who: Principal, subject: str) -> set[str]:
    return _roles(db, who, 11, subject) | _roles(db, who, 12, subject)


def _get(db: Session, who: Principal, concept_id: uuid.UUID, *, lock: bool = False) -> Concept:
    stmt = select(Concept).where(Concept.id == concept_id)
    c = db.scalar(stmt.with_for_update() if lock else stmt)
    if c is None or not _any_grade_roles(db, who, c.subject_code):
        raise NotFound("Concept not found.")  # outside the caller's subjects it doesn't exist for them
    return c


def _editable(db: Session, who: Principal, concept_id: uuid.UUID) -> Concept:
    c = _get(db, who, concept_id, lock=True)
    if "content_author" not in _any_grade_roles(db, who, c.subject_code):
        raise Forbidden("Only a content author in this subject can change concepts.")
    if c.status != "draft":
        raise Conflict("A published concept is frozen. Write a new concept and retire this one.")
    c.updated_at = func.now()
    return c


def create(db: Session, who: Principal, body: ConceptIn) -> Concept:
    if "content_author" not in _any_grade_roles(db, who, body.subject):
        raise Forbidden("Only a content author in this subject can write concepts.")
    c = Concept(
        code=body.code,
        subject_code=body.subject,
        title=body.title,
        statement=body.statement,
        created_by=who.user.id,
    )
    db.add(c)
    try:
        db.flush()
    except IntegrityError as e:
        db.rollback()
        raise Conflict("A concept with this code already exists.", code_reason="CODE_TAKEN") from e
    record(db, actor=who.user.id, action="concept.created", target_type="concept", target_id=str(c.id),
           details={"code": c.code})  # fmt: skip
    db.commit()
    return c


def update(db: Session, who: Principal, concept_id: uuid.UUID, body: ConceptPatch) -> Concept:
    c = _editable(db, who, concept_id)
    if body.title is not None:
        c.title = body.title
    if body.statement is not None:
        c.statement = body.statement
    if body.source_refs is not None:
        c.source_refs = [r.model_dump(mode="json") for r in body.source_refs]
    db.commit()
    return c


def set_topics(db: Session, who: Principal, concept_id: uuid.UUID, topic_ids: list[uuid.UUID]) -> Concept:
    from portal_api.modules.curriculum.models import BookEdition, Chapter, Grade, Subject, Topic

    c = _editable(db, who, concept_id)
    rows = db.execute(
        select(Topic.id, Grade.number, Subject.code)
        .join(Chapter, Chapter.id == Topic.chapter_id)
        .join(BookEdition, BookEdition.id == Chapter.book_id)
        .join(Grade, Grade.id == BookEdition.grade_id)
        .join(Subject, Subject.id == BookEdition.subject_id)
        .where(Topic.id.in_(topic_ids), Topic.retired_at.is_(None))
    ).all()
    if len(rows) != len(set(topic_ids)):
        raise Unprocessable("Some topics don't exist or are retired.")
    if any(subject != c.subject_code for _, _, subject in rows):
        raise Unprocessable("Map a concept only to topics of its own subject.")
    if any("content_author" not in _roles(db, who, grade, subject) for _, grade, subject in rows):
        raise Forbidden("You can map only topics in classes and subjects you author.")
    db.query(ConceptTopic).filter(ConceptTopic.concept_id == c.id).delete()
    for tid in sorted(set(topic_ids)):
        db.add(ConceptTopic(concept_id=c.id, topic_id=tid))
    record(db, actor=who.user.id, action="concept.topics_mapped", target_type="concept", target_id=str(c.id),
           details={"topics": len(set(topic_ids))})  # fmt: skip
    db.commit()
    return c


def _reaches(db: Session, start: uuid.UUID, target: uuid.UUID) -> bool:
    """Whether `start` already (transitively) requires `target`."""
    seen: set[uuid.UUID] = set()
    frontier = [start]
    while frontier:
        nxt = list(
            db.scalars(select(ConceptPrerequisite.requires_id).where(ConceptPrerequisite.concept_id.in_(frontier)))
        )
        if target in nxt:
            return True
        frontier = [n for n in nxt if n not in seen]
        seen.update(frontier)
    return False


def add_prerequisite(
    db: Session, who: Principal, concept_id: uuid.UUID, requires_id: uuid.UUID, bridging_lesson_id: uuid.UUID | None
) -> Concept:
    from portal_api.modules.content.models import Availability, ContentItem

    c = _get(db, who, concept_id, lock=True)
    if "content_author" not in _any_grade_roles(db, who, c.subject_code):
        raise Forbidden("Only a content author in this subject can change prerequisites.")
    if requires_id == c.id:
        raise Unprocessable("A concept can't be its own prerequisite.", code_reason="PREREQUISITE_CYCLE")
    req = db.get(Concept, requires_id)
    if req is None or req.status == "retired":
        raise Unprocessable("The prerequisite concept doesn't exist or is retired.")
    if bridging_lesson_id is not None:
        lesson = db.get(ContentItem, bridging_lesson_id)
        if lesson is None or lesson.kind != "lesson" or lesson.availability != Availability.live.value:
            raise Unprocessable("A bridging lesson must be a live lesson.")
        if lesson.subject_code != c.subject_code:
            raise Unprocessable("A bridging lesson must be a lesson of the concept's subject.")
    existing = db.scalar(
        select(ConceptPrerequisite).where(
            ConceptPrerequisite.concept_id == c.id, ConceptPrerequisite.requires_id == requires_id
        )
    )
    if existing is not None:
        existing.bridging_lesson_id = bridging_lesson_id or existing.bridging_lesson_id
        db.commit()
        return c
    if _reaches(db, requires_id, c.id):
        raise Unprocessable(
            "This would make a cycle: the prerequisite already depends on this concept.",
            code_reason="PREREQUISITE_CYCLE",
        )
    db.add(ConceptPrerequisite(concept_id=c.id, requires_id=requires_id, bridging_lesson_id=bridging_lesson_id))
    record(db, actor=who.user.id, action="concept.prerequisite_added", target_type="concept", target_id=str(c.id),
           details={"requires": str(requires_id)})  # fmt: skip
    db.commit()
    return c


def remove_prerequisite(db: Session, who: Principal, concept_id: uuid.UUID, requires_id: uuid.UUID) -> Concept:
    c = _get(db, who, concept_id, lock=True)
    if "content_author" not in _any_grade_roles(db, who, c.subject_code):
        raise Forbidden("Only a content author in this subject can change prerequisites.")
    db.query(ConceptPrerequisite).filter(
        ConceptPrerequisite.concept_id == c.id, ConceptPrerequisite.requires_id == requires_id
    ).delete()
    db.commit()
    return c


def publish(db: Session, who: Principal, concept_id: uuid.UUID) -> Concept:
    c = _get(db, who, concept_id, lock=True)
    if "subject_reviewer" not in _any_grade_roles(db, who, c.subject_code):
        raise Forbidden("Only a subject reviewer in this subject publishes concepts.")
    if c.created_by == who.user.id:
        raise Forbidden("A concept is published by an independent reviewer, not its author.")
    if c.status != "draft":
        raise Conflict(f"This concept is {c.status}.")
    problems = []
    if not c.source_refs:
        problems.append("Cite the source pages this outcome comes from.")
    if not db.scalar(select(func.count()).where(ConceptTopic.concept_id == c.id)):
        problems.append("Map the concept to at least one topic.")
    if problems:
        raise Unprocessable("This concept isn't ready to publish.", errors=problems)
    c.status, c.published_by, c.published_at = "published", who.user.id, func.now()
    record(db, actor=who.user.id, action="concept.published", target_type="concept", target_id=str(c.id),
           details={"code": c.code})  # fmt: skip
    db.commit()
    return c


def out(db: Session, c: Concept) -> dict[str, Any]:
    from portal_api.modules.curriculum.models import BookEdition, Chapter, Grade, Topic

    topics = db.execute(
        select(Topic, Chapter, Grade.number)
        .join(ConceptTopic, ConceptTopic.topic_id == Topic.id)
        .join(Chapter, Chapter.id == Topic.chapter_id)
        .join(BookEdition, BookEdition.id == Chapter.book_id)
        .join(Grade, Grade.id == BookEdition.grade_id)
        .where(ConceptTopic.concept_id == c.id)
        .order_by(Grade.number, Chapter.display_order, Topic.display_order)
    ).all()
    prereqs = db.scalars(select(ConceptPrerequisite).where(ConceptPrerequisite.concept_id == c.id))
    return {
        "id": c.id,
        "code": c.code,
        "subject": c.subject_code,
        "title": c.title,
        "statement": c.statement,
        "source_refs": c.source_refs,
        "status": c.status,
        "published_at": c.published_at,
        "topics": [
            {"topic_id": t.id, "number": t.number, "title": t.title, "grade": g, "chapter_number": ch.number}
            for t, ch, g in topics
        ],
        "prerequisites": [
            {"requires_id": p.requires_id, "bridging_lesson_id": p.bridging_lesson_id}
            for p in sorted(prereqs, key=lambda p: str(p.requires_id))
        ],
    }


def listing(db: Session, who: Principal, subject: str | None, grade: int | None) -> list[Concept]:
    from portal_api.modules.curriculum.models import BookEdition, Chapter, Grade, Topic

    stmt = select(Concept).order_by(Concept.code).limit(500)
    if subject:
        stmt = stmt.where(Concept.subject_code == subject)
    if grade:
        mapped = (
            select(ConceptTopic.concept_id)
            .join(Topic, Topic.id == ConceptTopic.topic_id)
            .join(Chapter, Chapter.id == Topic.chapter_id)
            .join(BookEdition, BookEdition.id == Chapter.book_id)
            .join(Grade, Grade.id == BookEdition.grade_id)
            .where(Grade.number == grade)
        )
        stmt = stmt.where(Concept.id.in_(mapped))
    return [c for c in db.scalars(stmt) if _any_grade_roles(db, who, c.subject_code)]


# ------------------------------------------------------------------ routes
router = APIRouter(prefix="/v1/studio", tags=["studio"])
DB = Annotated[Session, Depends(get_session)]


Member = Annotated[Principal, Depends(studio_member)]


class SourceRefIn(BaseModel):
    source_document_id: uuid.UUID
    pdf_from: int = Field(ge=1, le=5000)
    pdf_to: int = Field(ge=1, le=5000)


class ConceptIn(BaseModel):
    code: str = Field(pattern=CODE, description="Stable identifier, e.g. bio.cell.membrane-transport")
    title: str = Field(min_length=1, max_length=200)
    statement: str = Field(min_length=1, max_length=2000, description="The learning outcome")
    subject: Literal["biology", "chemistry", "physics", "computer_science", "mathematics"]


class ConceptPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    statement: str | None = Field(default=None, min_length=1, max_length=2000)
    source_refs: list[SourceRefIn] | None = Field(default=None, max_length=20)


class TopicsIn(BaseModel):
    topic_ids: list[uuid.UUID] = Field(max_length=200)


class PrerequisiteIn(BaseModel):
    requires_id: uuid.UUID
    bridging_lesson_id: uuid.UUID | None = None


class ConceptTopicOut(BaseModel):
    topic_id: uuid.UUID
    number: str | None
    title: str
    grade: int
    chapter_number: int


class PrerequisiteOut(BaseModel):
    requires_id: uuid.UUID
    bridging_lesson_id: uuid.UUID | None


class ConceptOut(BaseModel):
    id: uuid.UUID
    code: str
    subject: str
    title: str
    statement: str
    source_refs: list[dict[str, Any]]
    status: Literal["draft", "published", "retired"]
    published_at: datetime | None
    topics: list[ConceptTopicOut]
    prerequisites: list[PrerequisiteOut]


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


@router.get("/concepts", response_model=list[ConceptOut], summary="Learning concepts in your subjects")
def list_concepts(
    db: DB,
    who: Member,
    response: Response,
    subject: Annotated[str | None, Query(max_length=40)] = None,
    grade: Annotated[int | None, Query(ge=11, le=12)] = None,
) -> list[ConceptOut]:
    _private(response)
    return [ConceptOut(**out(db, c)) for c in listing(db, who, subject, grade)]


@router.post("/concepts", response_model=ConceptOut, status_code=201, summary="Write a draft learning concept")
def create_concept(db: DB, who: Member, body: ConceptIn, response: Response) -> ConceptOut:
    _private(response)
    return ConceptOut(**out(db, create(db, who, body)))


@router.get(
    "/concepts/{concept_id}", response_model=ConceptOut, summary="One concept with its topics and prerequisites"
)
def get_concept(db: DB, who: Member, concept_id: uuid.UUID, response: Response) -> ConceptOut:
    _private(response)
    return ConceptOut(**out(db, _get(db, who, concept_id)))


@router.put("/concepts/{concept_id}", response_model=ConceptOut, summary="Edit a draft concept")
def edit_concept(db: DB, who: Member, concept_id: uuid.UUID, body: ConceptPatch, response: Response) -> ConceptOut:
    _private(response)
    return ConceptOut(**out(db, update(db, who, concept_id, body)))


@router.put("/concepts/{concept_id}/topics", response_model=ConceptOut, summary="Map the topics that teach a concept")
def map_topics(db: DB, who: Member, concept_id: uuid.UUID, body: TopicsIn, response: Response) -> ConceptOut:
    _private(response)
    return ConceptOut(**out(db, set_topics(db, who, concept_id, body.topic_ids)))


@router.post(
    "/concepts/{concept_id}/prerequisites", response_model=ConceptOut, summary="Add a prerequisite (no cycles)"
)
def add_prereq(db: DB, who: Member, concept_id: uuid.UUID, body: PrerequisiteIn, response: Response) -> ConceptOut:
    _private(response)
    return ConceptOut(**out(db, add_prerequisite(db, who, concept_id, body.requires_id, body.bridging_lesson_id)))


@router.delete(
    "/concepts/{concept_id}/prerequisites/{requires_id}", response_model=ConceptOut, summary="Remove a prerequisite"
)
def remove_prereq(db: DB, who: Member, concept_id: uuid.UUID, requires_id: uuid.UUID, response: Response) -> ConceptOut:
    _private(response)
    return ConceptOut(**out(db, remove_prerequisite(db, who, concept_id, requires_id)))


@router.post(
    "/concepts/{concept_id}/publish",
    response_model=ConceptOut,
    summary="Publish a concept (an independent subject reviewer)",
)
def publish_concept(db: DB, who: Member, concept_id: uuid.UUID, response: Response) -> ConceptOut:
    _private(response)
    return ConceptOut(**out(db, publish(db, who, concept_id)))
