"""Controlled offline study packs (roadmap P13.S3.T1, §5.4 rule 6; OFFLINE-PACKS-01).

A pack is one chapter for one learner, built at request time, for reading and self-practice without a connection:

* **Lessons:** the chapter's live published lessons (one per concept, English first). Free previews always; premium
  lessons only under a current plan that covers the chapter's class and subject (ENTITLEMENT-SCOPE-01).
* **Practice:** only under such a plan, and only *practice-pool* multiple-choice questions whose published key and
  explanation are already released to learners (P08.S2.T3, AC14): never mock-reserved, quarantined, retired or draft
  versions, and never written questions. A question that needs a passage carries that passage's published version, or
  is left out; so is a question with diagrams (its files are served only inside an attempt), rather than packed without
  them. Timed and mock forms are never packed: a key on the device is fine for self-practice, never for a
  secure ranked test.
* **Files:** each diagram or handout a packed lesson names is listed with its SHA-256 and size; the app downloads it
  from the lesson's own file route, under the same rules as online.
* **Integrity and compatibility:** the content is one canonical JSON string; the manifest carries its SHA-256 and
  byte size, `pack_format_version` and `content_schema_version`. A client states the newest pack format it reads; it
  never receives a newer one (409 `PACK_FORMAT_UNSUPPORTED`, "update the app").
* **Expiry:** a pack with premium lessons or practice expires when the covering plan ends; a preview-only pack after
  30 days. `GET .../status` lets the app check, when online, whether to keep, refresh or delete a pack (P13.S3.T3).

Packs are never stored on the server or in a shared cache (`private, no-store`).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from portal_api.db import get_session
from portal_api.errors import Conflict, NotFound
from portal_api.modules.content import blocks, kinds
from portal_api.modules.content.models import Availability, ContentItem, ContentVersion
from portal_api.modules.curriculum.regions import book_is_released
from portal_api.modules.identity.deps import CurrentPrincipal

PACK_FORMAT_VERSION = 1
PREVIEW_PACK_DAYS = 30
QUESTION_FIELDS = ("stem", "options", "correct_option_id", "explanation", "passage_id", "marks")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _covering_end(db: Session, user_id: uuid.UUID, grade: int, subject: str) -> datetime | None:
    """The latest end among current plans covering this class and subject, if the trial-device rule allows use."""
    from portal_api.modules.access import service as access

    need = access.Need.subjects(grade, subject)
    if access.device_gate(db, user_id) is not None:
        return None
    ends = [e.ends_at for e in access.active_entitlements(db, user_id, access.db_now(db)) if access.covers(e, need)]
    return max(ends) if ends else None


def _lessons(db: Session, chapter_id: uuid.UUID, premium: bool) -> list[tuple[ContentItem, ContentVersion]]:
    rows = db.execute(
        select(ContentItem, ContentVersion)
        .join(ContentVersion, ContentVersion.id == ContentItem.published_version_id)
        .where(
            ContentItem.chapter_id == chapter_id,
            ContentItem.availability == Availability.live.value,
            ContentItem.kind.in_([k.name for k in kinds.KINDS.values() if k.learner_readable]),
        )
        .order_by(ContentVersion.published_at, ContentItem.id)
    ).all()
    concepts: dict[uuid.UUID, list[tuple[ContentItem, ContentVersion]]] = {}
    for i, v in rows:
        concepts.setdefault(i.concept_id or i.id, []).append((i, v))
    out = []
    for variants in concepts.values():
        i, v = next((iv for iv in variants if iv[0].language == "en"), variants[0])
        if i.access_tier == "preview" or premium:
            out.append((i, v))
    return out


def _questions(db: Session, chapter_id: uuid.UUID) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    from portal_api.modules.assessment.forms import passage_version

    rows = db.execute(
        select(ContentItem, ContentVersion)
        .join(ContentVersion, ContentVersion.id == ContentItem.published_version_id)
        .where(
            ContentItem.chapter_id == chapter_id,
            ContentItem.kind == "mcq",
            ContentItem.availability == Availability.live.value,  # quarantined and retired never leave the server
            ContentItem.question_pool == "practice",  # mock-reserved questions are never packed
        )
        .order_by(ContentItem.id)
    ).all()
    from portal_api.modules.content import assets

    questions, passages = [], {}
    for item, version in rows:
        body = version.body if isinstance(version.body, dict) else {}
        if assets.block_refs(body):
            continue  # its diagrams are served only inside an attempt today: left out, never shown without them
        if body.get("passage_id"):
            pvid = passage_version(db, version)
            if pvid is None:
                continue  # never a question without its passage
            pv = db.get(ContentVersion, pvid)
            if pv is None:
                continue
            passages[str(body["passage_id"])] = {"id": str(body["passage_id"]), "version": pv.number, "body": pv.body}
        questions.append(
            {
                "id": str(item.id),
                "version": version.number,
                "topic_id": str(item.topic_id) if item.topic_id else None,
                "body": {k: body[k] for k in QUESTION_FIELDS if k in body},
            }
        )
    return questions, passages


def build(db: Session, who: Any, chapter_id: uuid.UUID, client_format: int) -> dict[str, Any]:
    from portal_api.modules.content import assets
    from portal_api.modules.curriculum.models import BookEdition, Chapter

    if client_format < PACK_FORMAT_VERSION:
        raise Conflict(
            "This study pack needs a newer version of the app. Update the app to download it.",
            code_reason="PACK_FORMAT_UNSUPPORTED",
            pack_format_version=PACK_FORMAT_VERSION,
        )
    chapter = db.get(Chapter, chapter_id)
    book = db.get(BookEdition, chapter.book_id) if chapter is not None else None
    if chapter is None or book is None or chapter.retired_at is not None or not book_is_released(db, book):
        raise NotFound("Chapter not found.")
    grade, subject = book.grade.number, book.subject.code
    plan_end = _covering_end(db, who.user.id, grade, subject)
    from portal_api.modules.access.service import db_now

    now = db_now(db)
    lessons = _lessons(db, chapter_id, premium=plan_end is not None)
    questions, passages = _questions(db, chapter_id) if plan_end is not None else ([], {})
    files: list[dict[str, Any]] = []
    for item, version in lessons:
        for _, vid, _ in assets.block_refs(version.body):
            try:
                av, _asset = assets.for_lesson(db, item, uuid.UUID(vid))
            except (NotFound, ValueError):
                continue  # not servable to learners: never listed
            files.append(
                {
                    "lesson_id": str(item.id),
                    "asset_version_id": vid,
                    "media_type": av.delivery_media_type,
                    "sha256": av.delivery_sha256,
                    "url": f"/v1/lessons/{item.id}/assets/{vid}",
                }
            )
    content = {
        "lessons": [
            {
                "id": str(i.id),
                "version": v.number,
                "title": i.title,
                "language": i.language,
                "topic_id": str(i.topic_id) if i.topic_id else None,
                "access_tier": i.access_tier,
                "content_schema_version": v.content_schema_version,
                "block_types": v.block_types,
                "body": v.body,
                "source_refs": v.source_refs,
            }
            for i, v in lessons
        ],
        "questions": questions,
        "passages": sorted(passages.values(), key=lambda p: p["id"]),
    }
    text = _canonical(content)
    data = text.encode("utf-8")
    expires = plan_end if plan_end is not None else now + timedelta(days=PREVIEW_PACK_DAYS)
    manifest = {
        "pack_format_version": PACK_FORMAT_VERSION,
        "content_schema_version": blocks.CONTENT_SCHEMA_VERSION,
        "chapter_id": str(chapter_id),
        "grade": grade,
        "subject": subject,
        "generated_at": now.isoformat(),
        "expires_at": expires.isoformat(),
        "includes_premium": plan_end is not None,
        "lessons": len(content["lessons"]),
        "questions": len(questions),
        "files": files,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
    }
    return {"manifest": manifest, "content": text}


# ------------------------------------------------------------------ routes
router = APIRouter(prefix="/v1", tags=["study-packs"])
DB = Annotated[Session, Depends(get_session)]


class PackOut(BaseModel):
    manifest: dict[str, Any] = Field(description="Format and schema versions, expiry, counts, files, SHA-256 and size")
    content: str = Field(
        description="Canonical JSON (lessons, questions, passages); its UTF-8 SHA-256 is in the manifest"
    )


class PackStatusOut(BaseModel):
    keep: bool = Field(description="False: delete the pack from the device (plan ended or no longer covers it)")
    includes_premium: bool
    expires_at: datetime
    pack_format_version: int


@router.get(
    "/me/study-packs/{chapter_id}",
    response_model=PackOut,
    summary="An offline study pack for one chapter (lessons you may read; practice-pool questions with released keys)",
)
def study_pack(
    db: DB,
    who: CurrentPrincipal,
    chapter_id: uuid.UUID,
    response: Response,
    format: Annotated[int, Query(ge=1, le=100, description="The newest pack format this app reads")] = 1,
) -> PackOut:
    response.headers["Cache-Control"] = "private, no-store"
    from portal_api.modules.assessment import exam_room

    exam_room.guard(db, who.user.id)  # P10.S4.T3: packs carry released keys and explanations
    return PackOut(**build(db, who, chapter_id, format))


@router.get(
    "/me/study-packs/{chapter_id}/status",
    response_model=PackStatusOut,
    summary="Whether a downloaded pack may be kept, and until when (check when online)",
)
def study_pack_status(db: DB, who: CurrentPrincipal, chapter_id: uuid.UUID, response: Response) -> PackStatusOut:
    from portal_api.modules.access.service import db_now
    from portal_api.modules.curriculum.models import BookEdition, Chapter

    response.headers["Cache-Control"] = "private, no-store"
    chapter = db.get(Chapter, chapter_id)
    book = db.get(BookEdition, chapter.book_id) if chapter is not None else None
    if chapter is None or book is None or chapter.retired_at is not None or not book_is_released(db, book):
        return PackStatusOut(keep=False, includes_premium=False, expires_at=db_now(db), pack_format_version=1)
    plan_end = _covering_end(db, who.user.id, book.grade.number, book.subject.code)
    expires = plan_end if plan_end is not None else db_now(db) + timedelta(days=PREVIEW_PACK_DAYS)
    return PackStatusOut(
        keep=True, includes_premium=plan_end is not None, expires_at=expires, pack_format_version=PACK_FORMAT_VERSION
    )
