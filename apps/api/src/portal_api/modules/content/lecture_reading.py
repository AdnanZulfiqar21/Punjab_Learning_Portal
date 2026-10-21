"""A topic's lecture for learners (LECTURE-READ-01; Class XI Biology Chapter 1 pilot).

A topic offers a lecture only when an *academically approved* lecture (LECTURE-01: independent review, every check
passed) is pinned to a storyboard for that topic and its master video can be served. Everything else is "coming":
no production record, no draft, no unreviewed master ever reaches a learner.

Serving: the media provider (BLOCKERS B05) is not in place. In the development and test roles only, the API can
stream a master from a local directory (`PORTAL_LECTURE_MEDIA_DIR`) under the lecture's registered file name and
SHA-256-sized length, so the pilot can play on a phone on the same network. Deployed roles refuse that setting, so
nothing here becomes the production path by accident. Lectures are premium material: the stream follows the same
entitlement as a premium lesson of that class and subject; staff who can preview that subject may watch too.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from portal_api.config import get_settings
from portal_api.db import get_session, get_sessionmaker
from portal_api.errors import NotFound
from portal_api.modules.access import service as access
from portal_api.modules.content.lectures import Lecture
from portal_api.modules.content.models import ContentItem
from portal_api.modules.content.reading import _can_preview, _place
from portal_api.modules.identity.deps import Principal, optional_principal

Availability = Literal["available", "coming"]


class LectureMarkerOut(BaseModel):
    scene_id: str
    label: str
    start_s: int


class LectureSceneOut(BaseModel):
    scene_id: str
    text: str


class LearnerLectureOut(BaseModel):
    id: uuid.UUID
    title: str
    language: Literal["en", "ur", "roman_ur"]
    duration_s: int
    locked: bool = Field(description="True when this learner may not watch yet (plan or trial needed)")
    stream_path: str | None = Field(description="Where to stream the video; null while locked")
    markers: list[LectureMarkerOut]
    transcript: list[LectureSceneOut]


class TopicLectureOut(BaseModel):
    topic_id: uuid.UUID
    availability: Availability
    lectures: list[LearnerLectureOut] = Field(description="The topic's approved parts, in order; empty while coming")


def _part_key(title: str) -> tuple[int, str]:
    """Parts sort by their number ("Part 2" before "Part 10"); a single lecture has no part."""
    m = re.search(r"\bpart\s+(\d+)", title, re.I)
    return (int(m.group(1)) if m else 0, title.lower())


def _approved_for_topic(db: Session, topic_id: uuid.UUID) -> list[Lecture]:
    """The approved lectures whose storyboards belong to this topic, one per part, in part order."""
    rows = db.scalars(
        select(Lecture)
        .join(ContentItem, ContentItem.id == Lecture.storyboard_item_id)
        .where(ContentItem.topic_id == topic_id, Lecture.status == "approved")
        .order_by(Lecture.approved_at.desc())
    ).all()
    newest: dict[tuple[int, str], Lecture] = {}
    for lec in rows:  # the newest approval wins for the same part title
        newest.setdefault(_part_key(lec.title), lec)
    return [newest[k] for k in sorted(newest)]


def master_file(lec: Lecture) -> Path | None:
    """The master video on this machine, when the development media directory holds it; never outside that directory."""
    media_dir = get_settings().lecture_media_dir
    master = lec.master or {}
    name = str(master.get("filename") or "")
    if not media_dir or not name or Path(name).name != name:
        return None
    path = (Path(media_dir) / name).resolve()
    if not path.is_file() or Path(media_dir).resolve() not in path.parents:
        return None
    if int(master.get("bytes") or 0) != path.stat().st_size:
        return None  # a different file under the registered name is not the registered master
    return path


def _may_watch(db: Session, who: Principal | None, lec: Lecture) -> bool:
    if who is None:
        return False
    if _can_preview(db, who, lec.grade_number, lec.subject_code):
        return True
    return access.entitled_for(db, who.user.id, access.Need.subjects(lec.grade_number, lec.subject_code))


def _learner_out(db: Session, who: Principal | None, lec: Lecture) -> LearnerLectureOut:
    markers = [
        LectureMarkerOut(scene_id=str(m["scene_id"]), label=str(m.get("label") or ""), start_s=int(m["start_s"]))
        for m in (lec.markers or {}).get("scenes", [])
        if isinstance(m, dict) and "scene_id" in m and "start_s" in m
    ]
    transcript = [
        LectureSceneOut(scene_id=str(t.get("scene_id")), text=str(t.get("text") or "")) for t in lec.transcript
    ]
    locked = not _may_watch(db, who, lec)
    return LearnerLectureOut(
        id=lec.id,
        title=lec.title,
        language=lec.narration_language,  # type: ignore[arg-type]
        duration_s=int((lec.master or {}).get("duration_s") or 0),
        locked=locked,
        stream_path=None if locked else f"/v1/lectures/{lec.id}/stream",
        markers=markers,
        transcript=transcript,
    )


def topic_lecture(db: Session, who: Principal | None, topic_id: uuid.UUID) -> TopicLectureOut:
    topic, _chapter, _book = _place(db, topic_id)
    servable = [lec for lec in _approved_for_topic(db, topic.id) if master_file(lec) is not None]
    if not servable:
        return TopicLectureOut(topic_id=topic.id, availability="coming", lectures=[])
    return TopicLectureOut(
        topic_id=topic.id, availability="available", lectures=[_learner_out(db, who, lec) for lec in servable]
    )


router = APIRouter(prefix="/v1", tags=["lectures"])
DB = Annotated[Session, Depends(get_session)]
Who = Annotated[Principal | None, Depends(optional_principal)]


@router.get(
    "/topics/{topic_id}/lecture",
    response_model=TopicLectureOut,
    summary="The topic's approved lecture, or that it is coming",
)
def read_topic_lecture(db: DB, who: Who, topic_id: uuid.UUID) -> TopicLectureOut:
    return topic_lecture(db, who, topic_id)


@router.get(
    "/lectures/{lecture_id}/stream",
    summary="Stream an approved lecture's master video (development media directory only; range requests honoured)",
    response_class=FileResponse,
    responses={200: {"content": {"video/mp4": {}}}, 206: {"content": {"video/mp4": {}}}},
)
def stream_lecture(request: Request, lecture_id: uuid.UUID) -> FileResponse:
    # A stream lasts minutes: the caller, the lecture and the entitlement are resolved in a short session of its own
    # (no request-scoped dependency), released before the file is sent, so open players can't exhaust the pool.
    with get_sessionmaker()() as db:
        who = optional_principal(request, db)
        lec = db.get(Lecture, lecture_id)
        path = master_file(lec) if lec is not None and lec.status == "approved" else None
        if lec is None or path is None or not _may_watch(db, who, lec):
            raise NotFound("This lecture isn't available.")
    return FileResponse(
        path,
        media_type="video/mp4",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "Accept-Ranges": "bytes"},
    )
