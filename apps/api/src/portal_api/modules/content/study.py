"""Personal study tools (roadmap P11.S2.T2; STUDY-TOOLS-01).

Everything here belongs to one learner and is never shown to anyone else:

* **Lesson notes:** one private note per lesson the learner can read. Every change names the revision it was based on.
  An edit made from an older copy (another device or tab changed it meanwhile) is refused with `NOTE_CHANGED`, and an
  edit to a note deleted elsewhere with `NOTE_DELETED`; both return the current note so the learner chooses which to
  keep. Nothing is merged or overwritten silently. Deleting clears the text and keeps only the revision marker.
* **Topic favourites:** non-retired topics, one row each.
* **Saved formulas:** an equation block of a published lesson, pinned to the version it was saved from. If the lesson
  is published again later, the formula is marked `updated_since` so the learner checks the lesson: a reviewed
  correction is never hidden behind an old copy.

Timestamp bookmarks need the learner video player (lectures aren't published to learners yet), so they wait for it.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, SmallInteger, Text, UniqueConstraint, func, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.db import Base, get_session
from portal_api.errors import Conflict, NotFound, TooMany, Unprocessable
from portal_api.modules.content.models import ContentItem, ContentVersion
from portal_api.modules.identity.deps import CurrentPrincipal
from portal_api.modules.system.operations import requires_rollout

NOTE_MAX = 5000
FORMULAS_MAX = 500


class StudyNote(Base):
    __tablename__ = "study_note"
    __table_args__ = (UniqueConstraint("user_id", "item_id", name="uq_study_note_lesson"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_item.id", ondelete="RESTRICT"))
    text: Mapped[str] = mapped_column(Text, default="")
    revision: Mapped[int] = mapped_column(Integer, default=0)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TopicFavourite(Base):
    __tablename__ = "topic_favourite"
    __table_args__ = (UniqueConstraint("user_id", "topic_id", name="uq_topic_favourite"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"), index=True)
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topic.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SavedFormula(Base):
    __tablename__ = "saved_formula"
    __table_args__ = (UniqueConstraint("user_id", "version_id", "block_index", name="uq_saved_formula_block"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_item.id", ondelete="RESTRICT"))
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_version.id", ondelete="RESTRICT"))
    block_index: Mapped[int] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ------------------------------------------------------------------ notes
def _note_state(n: StudyNote | None, item_id: uuid.UUID) -> dict[str, Any]:
    if n is None:
        return {"lesson_id": item_id, "text": "", "revision": 0, "deleted": False, "updated_at": None}
    return {
        "lesson_id": n.item_id,
        "text": n.text,
        "revision": n.revision,
        "deleted": n.deleted_at is not None,
        "updated_at": n.updated_at,
    }


def _readable(db: Session, user_id: uuid.UUID, item_id: uuid.UUID) -> ContentItem:
    from portal_api.modules.content.completion import _readable_lesson

    return _readable_lesson(db, user_id, item_id)


def _locked_note(db: Session, user_id: uuid.UUID, item_id: uuid.UUID) -> StudyNote | None:
    return db.scalar(
        select(StudyNote).where(StudyNote.user_id == user_id, StudyNote.item_id == item_id).with_for_update()
    )


def get_note(db: Session, user_id: uuid.UUID, item_id: uuid.UUID) -> dict[str, Any]:
    _readable(db, user_id, item_id)
    n = db.scalar(select(StudyNote).where(StudyNote.user_id == user_id, StudyNote.item_id == item_id))
    return _note_state(n, item_id)


def save_note(db: Session, user_id: uuid.UUID, item_id: uuid.UUID, text: str, base_revision: int) -> dict[str, Any]:
    _readable(db, user_id, item_id)
    n = _locked_note(db, user_id, item_id)
    current = n.revision if n is not None else 0
    if base_revision != current:
        deleted = n is not None and n.deleted_at is not None
        raise Conflict(
            "This note was deleted on another device. Save again to keep your version."
            if deleted
            else "This note changed on another device. Choose which version to keep.",
            code_reason="NOTE_DELETED" if deleted else "NOTE_CHANGED",
            current=_jsonable(_note_state(n, item_id)),
        )
    if n is None:
        n = StudyNote(user_id=user_id, item_id=item_id)
        db.add(n)
    n.text, n.revision, n.deleted_at, n.updated_at = text, current + 1, None, func.now()
    db.commit()
    db.refresh(n)
    return _note_state(n, item_id)


def delete_note(db: Session, user_id: uuid.UUID, item_id: uuid.UUID, base_revision: int) -> dict[str, Any]:
    n = _locked_note(db, user_id, item_id)
    if n is None or n.deleted_at is not None:
        db.rollback()
        return _note_state(n, item_id)  # nothing to delete: already gone
    if base_revision != n.revision:
        raise Conflict(
            "This note changed on another device. Check it before deleting.",
            code_reason="NOTE_CHANGED",
            current=_jsonable(_note_state(n, item_id)),
        )
    n.text, n.revision, n.deleted_at, n.updated_at = "", n.revision + 1, func.now(), func.now()
    db.commit()
    db.refresh(n)
    return _note_state(n, item_id)


def notes(db: Session, user_id: uuid.UUID) -> list[dict[str, Any]]:
    from portal_api.modules.curriculum.models import Chapter

    rows = db.execute(
        select(StudyNote, ContentItem, Chapter)
        .join(ContentItem, ContentItem.id == StudyNote.item_id)
        .join(Chapter, Chapter.id == ContentItem.chapter_id)
        .where(StudyNote.user_id == user_id, StudyNote.deleted_at.is_(None))
        .order_by(StudyNote.updated_at.desc())
    ).all()
    return [
        {
            **_note_state(n, i.id),
            "lesson_title": i.title,
            "grade": i.grade_number,
            "subject": i.subject_code,
            "chapter_id": c.id,
            "chapter_number": c.number,
        }
        for n, i, c in rows
    ]


def _jsonable(state: dict[str, Any]) -> dict[str, Any]:
    out = dict(state)
    out["lesson_id"] = str(out["lesson_id"])
    out["updated_at"] = out["updated_at"].isoformat() if out["updated_at"] else None
    return out


# ------------------------------------------------------------------ favourites
def favourite(db: Session, user_id: uuid.UUID, topic_id: uuid.UUID, on: bool) -> None:
    from portal_api.modules.curriculum.models import Topic

    row = db.scalar(
        select(TopicFavourite).where(TopicFavourite.user_id == user_id, TopicFavourite.topic_id == topic_id)
    )
    if not on:
        if row is not None:
            db.delete(row)
            db.commit()
        return
    topic = db.get(Topic, topic_id)
    if topic is None or topic.retired_at is not None:
        raise NotFound("Topic not found.")
    if row is None:
        db.add(TopicFavourite(user_id=user_id, topic_id=topic_id))
        db.commit()


def favourites(db: Session, user_id: uuid.UUID) -> list[dict[str, Any]]:
    from portal_api.modules.curriculum.models import BookEdition, Chapter, Grade, Subject, Topic

    rows = db.execute(
        select(TopicFavourite, Topic, Chapter, Grade.number, Subject.code)
        .join(Topic, Topic.id == TopicFavourite.topic_id)
        .join(Chapter, Chapter.id == Topic.chapter_id)
        .join(BookEdition, BookEdition.id == Chapter.book_id)
        .join(Grade, Grade.id == BookEdition.grade_id)
        .join(Subject, Subject.id == BookEdition.subject_id)
        .where(TopicFavourite.user_id == user_id, Topic.retired_at.is_(None))
        .order_by(Grade.number, Subject.code, Chapter.display_order, Topic.display_order)
    ).all()
    return [
        {
            "topic_id": t.id,
            "number": t.number,
            "title": t.title,
            "grade": grade,
            "subject": subject,
            "chapter_id": c.id,
            "chapter_number": c.number,
            "chapter_title": c.title,
        }
        for _, t, c, grade, subject in rows
    ]


# ------------------------------------------------------------------ formulas
def save_formula(db: Session, user_id: uuid.UUID, item_id: uuid.UUID, block_index: int) -> SavedFormula:
    item = _readable(db, user_id, item_id)
    assert item.published_version_id is not None
    version = db.get(ContentVersion, item.published_version_id)
    blocks = (version.body or {}).get("blocks", []) if version is not None else []
    if not (0 <= block_index < len(blocks)) or blocks[block_index].get("type") != "equation":
        raise Unprocessable("Only a formula (an equation block) in this lesson can be saved.")
    existing = db.scalar(
        select(SavedFormula).where(
            SavedFormula.user_id == user_id,
            SavedFormula.version_id == item.published_version_id,
            SavedFormula.block_index == block_index,
        )
    )
    if existing is not None:
        return existing
    if (db.scalar(select(func.count()).where(SavedFormula.user_id == user_id)) or 0) >= FORMULAS_MAX:
        raise TooMany(f"You can keep up to {FORMULAS_MAX} formulas. Remove some to save more.")
    row = SavedFormula(user_id=user_id, item_id=item.id, version_id=item.published_version_id, block_index=block_index)
    db.add(row)
    db.commit()
    return row


def formulas(db: Session, user_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = db.execute(
        select(SavedFormula, ContentItem, ContentVersion)
        .join(ContentItem, ContentItem.id == SavedFormula.item_id)
        .join(ContentVersion, ContentVersion.id == SavedFormula.version_id)
        .where(SavedFormula.user_id == user_id)
        .order_by(SavedFormula.created_at.desc())
    ).all()
    out = []
    for f, item, version in rows:
        block = (version.body or {}).get("blocks", [])[f.block_index]
        out.append(
            {
                "id": f.id,
                "lesson_id": item.id,
                "lesson_title": item.title,
                "chapter_id": item.chapter_id,
                "grade": item.grade_number,
                "subject": item.subject_code,
                "latex": block.get("latex", ""),
                "text_alt": block.get("text_alt", ""),
                "saved_at": f.created_at,
                # A newer reviewed version exists: the learner should check the lesson, not trust the old copy.
                "updated_since": item.published_version_id != f.version_id,
            }
        )
    return out


def remove_formula(db: Session, user_id: uuid.UUID, formula_id: uuid.UUID) -> None:
    row = db.get(SavedFormula, formula_id)
    if row is None or row.user_id != user_id:
        raise NotFound("Formula not found.")
    db.delete(row)
    db.commit()


# ------------------------------------------------------------------ routes
# ROLLOUT-01: the whole study-tools surface follows its rollout flag (it only ever restricts).
router = APIRouter(prefix="/v1", tags=["study"], dependencies=[Depends(requires_rollout("study_tools"))])
DB = Annotated[Session, Depends(get_session)]


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


class NoteIn(BaseModel):
    text: Annotated[str, Field(max_length=NOTE_MAX)]
    base_revision: Annotated[int, Field(ge=0)]


class NoteOut(BaseModel):
    lesson_id: uuid.UUID
    text: str
    revision: int
    deleted: bool
    updated_at: datetime | None


class NoteListed(NoteOut):
    lesson_title: str
    grade: int
    subject: str
    chapter_id: uuid.UUID
    chapter_number: int


class FavouriteOut(BaseModel):
    topic_id: uuid.UUID
    number: str | None
    title: str
    grade: int
    subject: str
    chapter_id: uuid.UUID
    chapter_number: int
    chapter_title: str


class FormulaIn(BaseModel):
    lesson_id: uuid.UUID
    block_index: Annotated[int, Field(ge=0, le=500)]


class FormulaOut(BaseModel):
    id: uuid.UUID
    lesson_id: uuid.UUID
    lesson_title: str
    chapter_id: uuid.UUID
    grade: int
    subject: str
    latex: str
    text_alt: str
    saved_at: datetime
    updated_since: bool


@router.get("/me/lessons/{item_id}/note", response_model=NoteOut, summary="Your private note on a lesson")
def read_note(db: DB, who: CurrentPrincipal, item_id: uuid.UUID, response: Response) -> NoteOut:
    _private(response)
    return NoteOut(**get_note(db, who.user.id, item_id))


@router.put(
    "/me/lessons/{item_id}/note",
    response_model=NoteOut,
    summary="Save your note (refused with the current note if it changed or was deleted elsewhere)",
)
def write_note(db: DB, who: CurrentPrincipal, item_id: uuid.UUID, body: NoteIn, response: Response) -> NoteOut:
    _private(response)
    return NoteOut(**save_note(db, who.user.id, item_id, body.text, body.base_revision))


@router.delete("/me/lessons/{item_id}/note", response_model=NoteOut, summary="Delete your note on a lesson")
def remove_note(
    db: DB, who: CurrentPrincipal, item_id: uuid.UUID, response: Response, base_revision: Annotated[int, Query(ge=0)]
) -> NoteOut:
    _private(response)
    return NoteOut(**delete_note(db, who.user.id, item_id, base_revision))


@router.get("/me/notes", response_model=list[NoteListed], summary="All your lesson notes, newest first")
def list_notes(db: DB, who: CurrentPrincipal, response: Response) -> list[NoteListed]:
    _private(response)
    return [NoteListed(**n) for n in notes(db, who.user.id)]


@router.put("/me/favourites/topics/{topic_id}", status_code=204, summary="Add a topic to your favourites")
def add_favourite(db: DB, who: CurrentPrincipal, topic_id: uuid.UUID) -> Response:
    favourite(db, who.user.id, topic_id, True)
    return Response(status_code=204)


@router.delete("/me/favourites/topics/{topic_id}", status_code=204, summary="Remove a topic from your favourites")
def drop_favourite(db: DB, who: CurrentPrincipal, topic_id: uuid.UUID) -> Response:
    favourite(db, who.user.id, topic_id, False)
    return Response(status_code=204)


@router.get("/me/favourites", response_model=list[FavouriteOut], summary="Your favourite topics, in book order")
def list_favourites(db: DB, who: CurrentPrincipal, response: Response) -> list[FavouriteOut]:
    _private(response)
    return [FavouriteOut(**f) for f in favourites(db, who.user.id)]


@router.post("/me/formulas", response_model=FormulaOut, status_code=201, summary="Save a formula from a lesson")
def add_formula(db: DB, who: CurrentPrincipal, body: FormulaIn, response: Response) -> FormulaOut:
    _private(response)
    row = save_formula(db, who.user.id, body.lesson_id, body.block_index)
    return next(FormulaOut(**f) for f in formulas(db, who.user.id) if f["id"] == row.id)


@router.get("/me/formulas", response_model=list[FormulaOut], summary="Your saved formulas, newest first")
def list_formulas(db: DB, who: CurrentPrincipal, response: Response) -> list[FormulaOut]:
    _private(response)
    return [FormulaOut(**f) for f in formulas(db, who.user.id)]


@router.delete("/me/formulas/{formula_id}", status_code=204, summary="Remove a saved formula")
def drop_formula(db: DB, who: CurrentPrincipal, formula_id: uuid.UUID) -> Response:
    remove_formula(db, who.user.id, formula_id)
    return Response(status_code=204)
