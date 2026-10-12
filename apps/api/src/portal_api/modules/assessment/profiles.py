"""Versioned exam profiles with two-person verification (roadmap P05.S3.T1-T3, §10.5; EXAMPROFILE-01).

An exam profile is an official test pattern such as MDCAT, or one UET ECAT subject combination. Each **version**
pins everything a mock built from it uses:

* the year and the official source (link and note);
* duration and pinned late-write tolerance (default 0 ms for ranked mocks);
* marks per question and the negative marking;
* the invalid-item correction policy (EXCLUDE or CREDIT_ALL; KEY_CORRECTION is always reviewed separately);
* solution release;
* the sections, each a subject with question count and the classes it draws from.

Nothing here hard-codes current official numbers; they are entered as data and verified.

Lifecycle: `draft` → (two verifications by two different people, neither the author) → `verified` → `published`
(MFA). Publishing a newer version retires the previous one for **new** mocks only; attempts already built keep the
version they pinned. Drafts can be edited; nothing else can. Only published versions are visible to learners. A
profile carries an `eligibility_note` and a source link, and choosing a combination never claims admission
eligibility.

P05.S4.T3 (PROFILE-CHANGES-01): a pattern must resolve against the catalogue. Each section's class and subject needs
exactly one live book edition: none leaves the section nothing to draw from, and two (an old and a revised book both
live) would silently mix editions. This is checked when a draft is saved, again at publication and whenever a mock
is built, because the catalogue can change in between. A version for an older exam year can't replace a newer
published one.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.db import Base
from portal_api.errors import Conflict, Forbidden, NotFound, Unprocessable
from portal_api.modules.audit.models import record
from portal_api.modules.identity.deps import Principal

VERSION_STATUSES = ("draft", "verified", "published", "retired")


class ExamProfile(Base):
    __tablename__ = "exam_profile"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(40), unique=True)  # e.g. MDCAT, ECAT-PRE-ENGINEERING
    name: Mapped[str] = mapped_column(String(200))
    eligibility_note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExamProfileVersion(Base):
    __tablename__ = "exam_profile_version"
    __table_args__ = (
        UniqueConstraint("profile_id", "version", name="uq_exam_profile_version"),
        CheckConstraint(f"status in ({', '.join(repr(s) for s in VERSION_STATUSES)})", name="exam_profile_status"),
        Index(
            "uq_exam_profile_published",
            "profile_id",
            unique=True,
            postgresql_where=text("status = 'published'"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exam_profile.id", ondelete="RESTRICT"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    year: Mapped[int] = mapped_column(SmallInteger)
    status: Mapped[str] = mapped_column(String(10), default="draft")
    rules: Mapped[dict[str, Any]] = mapped_column(JSONB)  # validated ProfileRules
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    verifications: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)  # [{by, at, note}]
    published_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ------------------------------------------------------------------ rules
class Section(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str = Field(min_length=2, max_length=40)
    grades: list[Literal[11, 12]] = Field(min_length=1, max_length=2)
    questions: int = Field(ge=1, le=400)
    label: str = Field(default="", max_length=120)


class ProfileRules(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_url: str = Field(min_length=8, max_length=1000, pattern=r"^https?://")
    source_note: str = Field(min_length=10, max_length=2000, description="What was read, where, and when")
    duration_minutes: int = Field(ge=1, le=600)
    late_write_tolerance_ms: int = Field(default=0, ge=0, le=10_000)
    marks_per_question: int = Field(default=1, ge=1, le=10)
    negative_marks: int = Field(default=0, ge=0, le=10)
    invalid_item_treatment: Literal["EXCLUDE", "CREDIT_ALL"] = "EXCLUDE"
    solution_release: Literal["after_submission", "after_window"] = "after_submission"
    question_pool: Literal["mock", "any"] = Field(
        default="mock", description="mock: protected mock-only questions (P08.S3.T3); any: practice questions too"
    )
    sections: list[Section] = Field(min_length=1, max_length=12)
    streams: list[Literal["pre_medical", "pre_engineering", "ics"]] = Field(
        default_factory=list,
        description="Streams this pattern is for (P09.S4.T3); empty means every stream. Learners whose profile names "
        "another stream don't see it; learners without a stream see every pattern.",
    )


def parse_rules(raw: object, active_subjects: set[str]) -> tuple[ProfileRules | None, list[str]]:
    try:
        rules = ProfileRules.model_validate(raw)
    except ValidationError as e:
        return None, [f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors()]
    errors = []
    for n, s in enumerate(rules.sections, start=1):
        if s.subject not in active_subjects:
            errors.append(f"Section {n}: {s.subject} isn't an active subject.")
        for m, earlier in enumerate(rules.sections[: n - 1], start=1):
            # Sections sharing a subject and a class would draw on the same questions (GENERATOR-PROPERTIES-01).
            if earlier.subject == s.subject and set(earlier.grades) & set(s.grades):
                errors.append(f"Section {n}: {s.subject} classes overlap section {m}; give each class to one section.")
    if rules.negative_marks > rules.marks_per_question:
        errors.append("Negative marking can't exceed the marks for a question.")
    return (rules if not errors else None), errors


GRADE_NAMES = {11: "XI", 12: "XII"}


def catalogue_problems(db: Session, sections: list[dict[str, Any]]) -> list[str]:
    """Why a pattern's sections can't be drawn from the catalogue as it is now (empty when they can)."""
    from portal_api.modules.curriculum.models import BookEdition, Chapter, Grade, Subject

    problems = []
    for n, s in enumerate(sections, start=1):
        subject = db.scalar(select(Subject).where(Subject.code == s["subject"]))
        if subject is None or not subject.active:
            problems.append(f"Section {n}: {s['subject']} isn't offered now.")
            continue
        for g in s["grades"]:
            live = select(Chapter.id).where(Chapter.book_id == BookEdition.id, Chapter.retired_at.is_(None)).exists()
            books = db.execute(
                select(BookEdition.natural_key, BookEdition.title)
                .join(Grade, Grade.id == BookEdition.grade_id)
                .where(BookEdition.subject_id == subject.id, Grade.number == int(g), live)
                .order_by(BookEdition.natural_key)
            ).all()
            book = f"Class {GRADE_NAMES.get(int(g), g)} {subject.name}"
            if not books:
                problems.append(
                    f"Section {n}: the catalogue has no {book} book, so this section has nothing to draw from."
                )
            elif len(books) > 1:
                names = "; ".join(b.title or b.natural_key for b in books)
                problems.append(
                    f"Section {n}: the catalogue has {len(books)} {book} book editions ({names}), so this pattern "
                    "can't tell which one applies. Retire the edition that no longer applies first."
                )
    return problems


def total_questions(rules: dict[str, Any]) -> int:
    return sum(int(s["questions"]) for s in rules.get("sections", []))


# ------------------------------------------------------------------ service
def _active_subjects(db: Session) -> set[str]:
    from portal_api.modules.curriculum.models import Subject

    return set(db.scalars(select(Subject.code).where(Subject.active)))


def create_profile(db: Session, who: Principal, code: str, name: str, eligibility_note: str) -> ExamProfile:
    code = code.strip().upper()
    if db.scalar(select(ExamProfile.id).where(ExamProfile.code == code)):
        raise Conflict("A profile with that code already exists.")
    p = ExamProfile(
        id=uuid.uuid4(), code=code, name=name.strip(), eligibility_note=eligibility_note.strip(), created_by=who.user.id
    )
    db.add(p)
    record(db, actor=who.user.id, action="exam_profile.created", target_type="exam_profile", target_id=str(p.id))
    db.commit()
    db.refresh(p)
    return p


def _profile(db: Session, profile_id: uuid.UUID) -> ExamProfile:
    p = db.get(ExamProfile, profile_id)
    if p is None:
        raise NotFound("Exam profile not found.")
    return p


def _version(db: Session, version_id: uuid.UUID, *, for_update: bool = False) -> ExamProfileVersion:
    stmt = select(ExamProfileVersion).where(ExamProfileVersion.id == version_id)
    v = db.scalar(stmt.with_for_update() if for_update else stmt)
    if v is None:
        raise NotFound("Profile version not found.")
    return v


def save_draft(
    db: Session, who: Principal, profile_id: uuid.UUID, year: int, rules: object, version_id: uuid.UUID | None = None
) -> ExamProfileVersion:
    _profile(db, profile_id)
    parsed, errors = parse_rules(rules, _active_subjects(db))
    if not 2020 <= year <= 2100:
        errors = [f"year: {year} isn't a supported exam year; enter a year from 2020 to 2100.", *errors]
    if parsed is not None:
        errors += catalogue_problems(db, parsed.model_dump(mode="json")["sections"])
    if errors or parsed is None:
        raise Unprocessable("The profile rules aren't valid.", errors=errors)
    if version_id is not None:
        v = _version(db, version_id, for_update=True)
        if v.profile_id != profile_id:
            raise NotFound("Profile version not found.")
        if v.status != "draft":
            raise Conflict("Only drafts can be edited; start a new version instead.")
        v.year, v.rules, v.verifications = year, parsed.model_dump(mode="json"), []  # edits clear verifications
    else:
        latest = db.scalar(
            select(func.max(ExamProfileVersion.version)).where(ExamProfileVersion.profile_id == profile_id)
        )
        v = ExamProfileVersion(
            id=uuid.uuid4(),
            profile_id=profile_id,
            version=(latest or 0) + 1,
            year=year,
            status="draft",
            rules=parsed.model_dump(mode="json"),
            created_by=who.user.id,
            verifications=[],
        )
        db.add(v)
    record(
        db,
        actor=who.user.id,
        action="exam_profile.draft_saved",
        target_type="exam_profile_version",
        target_id=str(v.id),
        details={"version": v.version, "year": year, "questions": total_questions(v.rules)},
    )
    db.commit()
    db.refresh(v)
    return v


def verify(db: Session, who: Principal, version_id: uuid.UUID, note: str) -> ExamProfileVersion:
    """One of two independent checks of the source, year and rules. The author never verifies their own draft."""
    v = _version(db, version_id, for_update=True)
    if v.status not in ("draft", "verified"):
        raise Conflict("Only drafts are verified.")
    if v.created_by == who.user.id:
        raise Forbidden("The author of a profile version can't verify it.")
    if any(x["by"] == str(who.user.id) for x in v.verifications):
        raise Conflict("You have already verified this version; a second person must verify it.")
    if len(v.verifications) >= 2:
        raise Conflict("This version already has two verifications.")
    now = db.execute(select(func.now())).scalar_one()
    v.verifications = [*v.verifications, {"by": str(who.user.id), "at": now.isoformat(), "note": note.strip()}]
    if len(v.verifications) == 2:
        v.status = "verified"
    record(
        db,
        actor=who.user.id,
        action="exam_profile.verified",
        target_type="exam_profile_version",
        target_id=str(v.id),
        details={"count": len(v.verifications), "note": note.strip()},
    )
    db.commit()
    db.refresh(v)
    return v


def publish(db: Session, who: Principal, version_id: uuid.UUID) -> ExamProfileVersion:
    v = _version(db, version_id, for_update=True)
    if v.status != "verified":
        raise Conflict("A version needs two independent verifications before it can be published.")
    current = db.scalar(
        select(ExamProfileVersion)
        .where(ExamProfileVersion.profile_id == v.profile_id, ExamProfileVersion.status == "published")
        .with_for_update()
    )
    if current is not None and current.year > v.year:
        raise Conflict(
            f"Version {v.version} is for {v.year}, older than the published version {current.version} for "
            f"{current.year}. Publish a version for {current.year} or later instead."
        )
    problems = catalogue_problems(db, v.rules["sections"])  # the catalogue may have changed since the draft
    if problems:
        raise Conflict("This version doesn't match the catalogue as it is now.", errors=problems)
    now = db.execute(select(func.now())).scalar_one()
    if current is not None:
        current.status, current.retired_at = "retired", now
        db.flush()  # one published version per profile
    v.status, v.published_by, v.published_at = "published", who.user.id, now
    record(
        db,
        actor=who.user.id,
        action="exam_profile.published",
        target_type="exam_profile_version",
        target_id=str(v.id),
        details={"version": v.version, "retired": str(current.id) if current else None},
    )
    db.commit()
    db.refresh(v)
    return v


def profiles(db: Session) -> list[tuple[ExamProfile, list[ExamProfileVersion]]]:
    out = []
    for p in db.scalars(select(ExamProfile).order_by(ExamProfile.code)):
        versions = list(
            db.scalars(
                select(ExamProfileVersion)
                .where(ExamProfileVersion.profile_id == p.id)
                .order_by(ExamProfileVersion.version)
            )
        )
        out.append((p, versions))
    return out


def published(db: Session) -> list[tuple[ExamProfile, ExamProfileVersion]]:
    return [
        (p, v)
        for p, v in db.execute(
            select(ExamProfile, ExamProfileVersion)
            .join(ExamProfileVersion, ExamProfileVersion.profile_id == ExamProfile.id)
            .where(ExamProfileVersion.status == "published")
            .order_by(ExamProfile.code)
        ).all()
    ]
