"""Lecture production records (roadmap P07.S4.T3 finished-media review, P07.S3.T1 captions and transcripts;
LECTURE-01).

Premium animated lectures are produced outside the portal (narration, animation, editing). The portal keeps the
traceable record that makes one academically approvable, separate from platform code:

* a **narration voice registry**: each voice has a language (Roman Urdu, Urdu or English), the production tool and
  the tool's voice reference. Only the owner approves a voice (MFA, with evidence), so every lecture in a language
  sounds consistent; a retired voice can't start new lectures;
* a **lecture** pins one *published* storyboard version (its scenes, claims and textbook source references) and
  inherits its class, subject and chapter, so Class 11 and 12 never mix. It names its narration language and an
  approved voice in that language;
* the **master video** is registered by file name, SHA-256, size and duration, and where the owner keeps it. Storing
  and serving video waits on object storage and the media provider (B03, B05);
* an **editable transcript**, one entry per storyboard scene, starting from the storyboard's narration;
* **captions** per language: reviewed WebVTT versions in the asset archive (ASSETS-01), same class and subject;
* **chapter markers** (P07.S3.T2, MARKERS-01): where each storyboard scene starts in the master, keyed by the
  storyboard's stable scene ids (so a learner's later bookmark can say "scene s3, 12 s in" and stay meaningful when the
  video is replaced) and pinned to the master's SHA-256. A new master marks them for re-timing; submission needs
  current markers;
* an **independent review**: a subject reviewer in scope who didn't produce the lecture checks accuracy, voice/text
  alignment, pacing, spelling, diagrams, captions, rights and textbook-source verification, and notes scientific
  terms and pronunciation. Only an approving review with every check passed makes a lecture *academically
  approved*. Generation or upload success never does. An approved lecture is frozen.

Nothing here is shown to learners yet: learner playback needs the media provider (B05).
"""

from __future__ import annotations

import itertools
import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, SmallInteger, String, Text, UniqueConstraint, func, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.db import Base, get_session
from portal_api.errors import Conflict, Forbidden, NotFound, Unprocessable
from portal_api.modules.audit.models import record
from portal_api.modules.content.router import studio_member
from portal_api.modules.identity.deps import Principal, current_principal, require
from portal_api.modules.identity.permissions import Permission

LANGUAGES = ("roman_ur", "ur", "en")
LANGUAGE_NAME = {"roman_ur": "Roman Urdu", "ur": "Urdu", "en": "English"}
CHECKLIST = (
    "accuracy",
    "voice_text_alignment",
    "pacing",
    "spelling",
    "diagrams",
    "captions",
    "rights",
    "source_verification",
)
EDITABLE = ("in_production", "changes_requested")


class NarrationVoice(Base):
    __tablename__ = "narration_voice"
    __table_args__ = (
        UniqueConstraint("name", name="uq_narration_voice_name"),
        CheckConstraint("language in ('roman_ur','ur','en')", name="narration_voice_language"),
        CheckConstraint("status in ('proposed','approved','retired')", name="narration_voice_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    language: Mapped[str] = mapped_column(String(10))
    tool: Mapped[str] = mapped_column(String(120))
    voice_ref: Mapped[str] = mapped_column(String(200))
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(10), default="proposed")
    proposed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approval_evidence: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Lecture(Base):
    __tablename__ = "lecture"
    __table_args__ = (
        CheckConstraint("narration_language in ('roman_ur','ur','en')", name="lecture_language"),
        CheckConstraint(
            "status in ('in_production','in_review','approved','changes_requested')", name="lecture_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    storyboard_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_item.id", ondelete="RESTRICT"))
    storyboard_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_version.id", ondelete="RESTRICT"))
    grade_number: Mapped[int] = mapped_column(SmallInteger)
    subject_code: Mapped[str] = mapped_column(String(40))
    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chapter.id", ondelete="RESTRICT"), index=True)
    title: Mapped[str] = mapped_column(Text)
    narration_language: Mapped[str] = mapped_column(String(10))
    voice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("narration_voice.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(18), default="in_production")
    master: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    transcript: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    captions: Mapped[dict[str, str]] = mapped_column(JSONB, default=dict)
    # MARKERS-01: {"master_sha256": ..., "scenes": [{"scene_id", "start_s", "label"}]}, timed against that master.
    markers: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    review: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    contributors: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ------------------------------------------------------------------ schemas
class VoiceIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    language: Literal["roman_ur", "ur", "en"]
    tool: str = Field(min_length=2, max_length=120, description="The production tool or provider")
    voice_ref: str = Field(min_length=1, max_length=200, description="The tool's own voice identifier")
    notes: str = Field(default="", max_length=2000)


class EvidenceIn(BaseModel):
    evidence: str = Field(min_length=10, max_length=2000)


class VoiceOut(BaseModel):
    id: uuid.UUID
    name: str
    language: str
    tool: str
    voice_ref: str
    notes: str
    status: Literal["proposed", "approved", "retired"]
    approved_at: datetime | None
    approval_evidence: str | None


class LectureIn(BaseModel):
    storyboard_item_id: uuid.UUID
    narration_language: Literal["roman_ur", "ur", "en"]
    voice_id: uuid.UUID
    title: str | None = Field(default=None, max_length=200)


class MasterIn(BaseModel):
    filename: str = Field(min_length=3, max_length=255)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bytes: int = Field(ge=1)
    duration_s: int = Field(ge=1, le=7200)
    location: str = Field(min_length=3, max_length=500, description="Where the owner keeps the master")


class TranscriptScene(BaseModel):
    scene_id: str = Field(min_length=1, max_length=20)
    text: str = Field(min_length=1, max_length=4000)


class TranscriptIn(BaseModel):
    scenes: list[TranscriptScene] = Field(max_length=60)


class MarkerIn(BaseModel):
    scene_id: str = Field(min_length=1, max_length=20)
    start_s: int = Field(ge=0, le=7200)
    label: str = Field(
        min_length=1, max_length=120, description="The concept section a learner sees in the chapter list"
    )


class MarkersIn(BaseModel):
    scenes: list[MarkerIn] = Field(max_length=60)


class CaptionIn(BaseModel):
    language: Literal["roman_ur", "ur", "en"]
    asset_version_id: uuid.UUID


class ReviewIn(BaseModel):
    decision: Literal["approve", "request_changes"]
    checklist: dict[str, bool] = Field(default_factory=dict)
    notes: str = Field(min_length=10, max_length=4000, description="Terms, pronunciation, equations, timing")


class LectureOut(BaseModel):
    id: uuid.UUID
    title: str
    storyboard_item_id: uuid.UUID
    storyboard_version: int
    grade: int
    subject: str
    chapter_id: uuid.UUID
    narration_language: str
    voice: VoiceOut
    status: Literal["in_production", "in_review", "approved", "changes_requested"]
    academically_approved: bool = Field(description="True only after an independent reviewer approved every check")
    master: dict[str, Any] | None
    transcript: list[dict[str, Any]]
    captions: dict[str, str]
    markers: dict[str, Any] | None
    markers_current: bool = Field(description="Timed against the current master video")
    marker_proposal: list[dict[str, Any]] = Field(description="Starting point: the storyboard's planned scene times")
    review: dict[str, Any] | None
    missing: list[str] = Field(description="What still blocks submission for review")
    approved_at: datetime | None
    updated_at: datetime


# ------------------------------------------------------------------ helpers
def _roles(db: Session, who: Principal, grade: int, subject: str) -> set[str]:
    from portal_api.modules.content.workflow import roles_in_scope

    return {r.value for r in roles_in_scope(db, who.user.id, grade, subject)}


def _voice_out(v: NarrationVoice) -> VoiceOut:
    return VoiceOut(
        id=v.id,
        name=v.name,
        language=v.language,
        tool=v.tool,
        voice_ref=v.voice_ref,
        notes=v.notes,
        status=v.status,  # type: ignore[arg-type]
        approved_at=v.approved_at,
        approval_evidence=v.approval_evidence,
    )


def _missing(db: Session, lec: Lecture) -> list[str]:
    from portal_api.modules.content.models import ContentVersion

    out = []
    if lec.master is None:
        out.append("Register the master video (file name, SHA-256, size, duration, where it is kept).")
    version = db.get(ContentVersion, lec.storyboard_version_id)
    scene_ids = [s.get("id") for s in (version.body or {}).get("scenes", [])] if version is not None else []
    if [t.get("scene_id") for t in lec.transcript] != scene_ids:
        out.append("The transcript needs one entry for every storyboard scene, in order.")
    if lec.master is not None and lec.markers is None:
        out.append("Mark where each scene starts in the master video (chapter markers).")
    elif lec.master is not None and not _markers_current(lec):
        out.append("The master video changed since the chapter markers were set; re-time them.")
    if lec.narration_language not in lec.captions:
        out.append(f"Attach reviewed {LANGUAGE_NAME[lec.narration_language]} captions from the asset archive.")
    for lang, vid in lec.captions.items():
        out += [f"{LANGUAGE_NAME[lang]} captions: {p}" for p in _caption_problems(db, lec, vid)]
    voice = db.get(NarrationVoice, lec.voice_id)
    if voice is None or voice.status != "approved":
        out.append("The narration voice is no longer approved; choose an approved voice.")
    return out


def _scenes(db: Session, lec: Lecture) -> list[dict[str, Any]]:
    from portal_api.modules.content.models import ContentVersion

    version = db.get(ContentVersion, lec.storyboard_version_id)
    return list((version.body or {}).get("scenes", [])) if version is not None else []


def _markers_current(lec: Lecture) -> bool:
    return bool(lec.markers and lec.master and lec.markers.get("master_sha256") == lec.master.get("sha256"))


def _caption_problems(db: Session, lec: Lecture, version_id: str) -> list[str]:
    from portal_api.modules.content import assets

    v = assets.resolve(db, version_id)
    a = db.get(assets.Asset, v.asset_id) if v is not None else None
    if v is None or a is None:
        return [f"asset version {version_id} isn't in the asset archive."]
    problems = []
    if a.kind != "caption":
        problems.append(f"'{a.title}' isn't a captions file.")
    if (a.grade_number, a.subject_code) != (lec.grade_number, lec.subject_code):
        problems.append(f"'{a.title}' belongs to another class or subject; Class 11 and 12 are never mixed.")
    if v.delivery_state != "ready":
        problems.append(f"'{a.title}' version {v.number} has no ready copy.")
    return problems


def _out(db: Session, lec: Lecture) -> LectureOut:
    from portal_api.modules.content.models import ContentVersion

    voice = db.get(NarrationVoice, lec.voice_id)
    version = db.get(ContentVersion, lec.storyboard_version_id)
    assert voice is not None and version is not None
    return LectureOut(
        id=lec.id,
        title=lec.title,
        storyboard_item_id=lec.storyboard_item_id,
        storyboard_version=version.number,
        grade=lec.grade_number,
        subject=lec.subject_code,
        chapter_id=lec.chapter_id,
        narration_language=lec.narration_language,
        voice=_voice_out(voice),
        status=lec.status,  # type: ignore[arg-type]
        academically_approved=lec.status == "approved",
        master=lec.master,
        transcript=lec.transcript,
        captions=lec.captions,
        markers=lec.markers,
        markers_current=_markers_current(lec),
        marker_proposal=[
            {
                "scene_id": s.get("id"),
                "start_s": s.get("start_s", 0),
                "label": str(s.get("on_screen_text") or s.get("id") or "")[:120],
            }
            for s in _scenes(db, lec)
        ],
        review=lec.review,
        missing=_missing(db, lec) if lec.status in EDITABLE else [],
        approved_at=lec.approved_at,
        updated_at=lec.updated_at,
    )


def _get(db: Session, who: Principal, lecture_id: uuid.UUID, *, for_update: bool = False) -> Lecture:
    stmt = select(Lecture).where(Lecture.id == lecture_id)
    lec = db.scalar(stmt.with_for_update() if for_update else stmt)
    if lec is None or not _roles(db, who, lec.grade_number, lec.subject_code) & CONTENT_ROLES:
        raise NotFound("Lecture not found.")  # don't reveal lectures outside the caller's scope
    return lec


CONTENT_ROLES = {"content_author", "subject_reviewer", "publisher", "academic_adjudicator"}


def _editable(db: Session, who: Principal, lecture_id: uuid.UUID) -> Lecture:
    lec = _get(db, who, lecture_id, for_update=True)
    if "content_author" not in _roles(db, who, lec.grade_number, lec.subject_code):
        raise Forbidden("Only a content author in this class and subject can produce lectures.")
    if lec.status not in EDITABLE:
        raise Conflict(f"This lecture is {lec.status.replace('_', ' ')}; it can't be changed now.")
    if str(who.user.id) not in lec.contributors:
        lec.contributors = [*lec.contributors, str(who.user.id)]
    lec.updated_at = func.now()
    return lec


# ------------------------------------------------------------------ routes
router = APIRouter(prefix="/v1/studio", tags=["lectures"])
DB = Annotated[Session, Depends(get_session)]
Signed = Annotated[Principal, Depends(current_principal)]
Member = Annotated[Principal, Depends(studio_member)]  # content staff only
Reviewer = Annotated[Principal, Depends(require(Permission.review_content))]
Author = Annotated[Principal, Depends(require(Permission.draft_content))]
VoiceApprover = Annotated[Principal, Depends(require(Permission.approve_voices))]


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


@router.get("/voices", response_model=list[VoiceOut], summary="Narration voices (proposed, approved, retired)")
def list_voices(db: DB, who: Signed, response: Response) -> list[VoiceOut]:
    _private(response)
    if not ({r.value for r in who.roles} & (CONTENT_ROLES | {"owner_admin"})):
        raise Forbidden("Narration voices are for content staff.")
    return [
        _voice_out(v) for v in db.scalars(select(NarrationVoice).order_by(NarrationVoice.language, NarrationVoice.name))
    ]


@router.post("/voices", response_model=VoiceOut, status_code=201, summary="Propose a narration voice")
def propose_voice(db: DB, who: Author, body: VoiceIn) -> VoiceOut:
    if db.scalar(select(NarrationVoice.id).where(NarrationVoice.name == body.name.strip())) is not None:
        raise Conflict("A voice with this name already exists.")
    v = NarrationVoice(
        name=body.name.strip(),
        language=body.language,
        tool=body.tool.strip(),
        voice_ref=body.voice_ref.strip(),
        notes=body.notes.strip(),
        proposed_by=who.user.id,
    )
    db.add(v)
    db.flush()
    record(db, actor=who.user.id, action="voice.proposed", target_type="narration_voice", target_id=str(v.id))
    db.commit()
    return _voice_out(v)


def _set_voice_status(db: Session, who: Principal, voice_id: uuid.UUID, status: str, evidence: str) -> VoiceOut:
    v = db.scalar(select(NarrationVoice).where(NarrationVoice.id == voice_id).with_for_update())
    if v is None:
        raise NotFound("Voice not found.")
    v.status = status
    if status == "approved":
        v.approved_by, v.approved_at, v.approval_evidence = who.user.id, func.now(), evidence
    record(db, actor=who.user.id, action=f"voice.{status}", target_type="narration_voice", target_id=str(v.id),
           details={"evidence": evidence})  # fmt: skip
    db.commit()
    db.refresh(v)
    return _voice_out(v)


@router.post("/voices/{voice_id}/approve", response_model=VoiceOut, summary="Owner approves a voice (MFA, evidence)")
def approve_voice(db: DB, who: VoiceApprover, voice_id: uuid.UUID, body: EvidenceIn) -> VoiceOut:
    return _set_voice_status(db, who, voice_id, "approved", body.evidence)


@router.post("/voices/{voice_id}/retire", response_model=VoiceOut, summary="Owner retires a voice (MFA, reason)")
def retire_voice(db: DB, who: VoiceApprover, voice_id: uuid.UUID, body: EvidenceIn) -> VoiceOut:
    return _set_voice_status(db, who, voice_id, "retired", body.evidence)


@router.get("/lectures", response_model=list[LectureOut], summary="Lecture production records in your scope")
def list_lectures(db: DB, who: Member, response: Response) -> list[LectureOut]:
    _private(response)
    rows = db.scalars(select(Lecture).order_by(Lecture.updated_at.desc()).limit(200))
    return [_out(db, x) for x in rows if _roles(db, who, x.grade_number, x.subject_code) & CONTENT_ROLES]


@router.post("/lectures", response_model=LectureOut, status_code=201, summary="Start a lecture from a storyboard")
def create_lecture(db: DB, who: Author, body: LectureIn) -> LectureOut:
    from portal_api.modules.content.models import ContentItem, ContentVersion

    item = db.get(ContentItem, body.storyboard_item_id)
    if item is None or item.kind != "storyboard":
        raise NotFound("Storyboard not found.")
    if "content_author" not in _roles(db, who, item.grade_number, item.subject_code):
        raise NotFound("Storyboard not found.")
    if item.published_version_id is None:
        raise Unprocessable("A lecture starts from a reviewed, published storyboard.", code_reason="STORYBOARD")
    voice = db.get(NarrationVoice, body.voice_id)
    if voice is None or voice.status != "approved":
        raise Unprocessable("Choose a narration voice the owner has approved.", code_reason="VOICE")
    if voice.language != body.narration_language:
        raise Unprocessable(
            f"'{voice.name}' narrates {LANGUAGE_NAME[voice.language]}, not {LANGUAGE_NAME[body.narration_language]}.",
            code_reason="VOICE",
        )
    version = db.get(ContentVersion, item.published_version_id)
    assert version is not None
    scenes = (version.body or {}).get("scenes", [])
    lec = Lecture(
        storyboard_item_id=item.id,
        storyboard_version_id=version.id,
        grade_number=item.grade_number,
        subject_code=item.subject_code,
        chapter_id=item.chapter_id,
        title=(body.title or item.title).strip(),
        narration_language=body.narration_language,
        voice_id=voice.id,
        transcript=[{"scene_id": s.get("id"), "text": s.get("narration", "")} for s in scenes],
        captions={},
        contributors=[str(who.user.id)],
        created_by=who.user.id,
    )
    db.add(lec)
    db.flush()
    record(db, actor=who.user.id, action="lecture.created", target_type="lecture", target_id=str(lec.id),
           details={"storyboard_version_id": str(version.id), "voice_id": str(voice.id)})  # fmt: skip
    db.commit()
    db.refresh(lec)
    return _out(db, lec)


@router.get("/lectures/{lecture_id}", response_model=LectureOut, summary="A lecture production record")
def get_lecture(db: DB, who: Member, lecture_id: uuid.UUID, response: Response) -> LectureOut:
    _private(response)
    return _out(db, _get(db, who, lecture_id))


@router.put("/lectures/{lecture_id}/master", response_model=LectureOut, summary="Register the master video")
def set_master(db: DB, who: Author, lecture_id: uuid.UUID, body: MasterIn) -> LectureOut:
    lec = _editable(db, who, lecture_id)
    lec.master = body.model_dump()
    record(db, actor=who.user.id, action="lecture.master_registered", target_type="lecture", target_id=str(lec.id),
           details={"sha256": body.sha256, "bytes": body.bytes})  # fmt: skip
    db.commit()
    db.refresh(lec)
    return _out(db, lec)


@router.put("/lectures/{lecture_id}/transcript", response_model=LectureOut, summary="Edit the per-scene transcript")
def set_transcript(db: DB, who: Author, lecture_id: uuid.UUID, body: TranscriptIn) -> LectureOut:
    from portal_api.modules.content.models import ContentVersion

    lec = _editable(db, who, lecture_id)
    version = db.get(ContentVersion, lec.storyboard_version_id)
    scene_ids = [s.get("id") for s in (version.body or {}).get("scenes", [])] if version is not None else []
    if [s.scene_id for s in body.scenes] != scene_ids:
        raise Unprocessable("Give one transcript entry for every storyboard scene, in order.", scenes=scene_ids)
    lec.transcript = [s.model_dump() for s in body.scenes]
    db.commit()
    db.refresh(lec)
    return _out(db, lec)


@router.put(
    "/lectures/{lecture_id}/markers",
    response_model=LectureOut,
    summary="Set where each storyboard scene starts in the current master video (chapter markers)",
)
def set_markers(db: DB, who: Author, lecture_id: uuid.UUID, body: MarkersIn) -> LectureOut:
    lec = _editable(db, who, lecture_id)
    if lec.master is None:
        raise Unprocessable("Register or upload the master video first; markers are timed against it.")
    scene_ids = [s.get("id") for s in _scenes(db, lec)]
    errors = []
    if [m.scene_id for m in body.scenes] != scene_ids:
        errors.append("Give one marker for every storyboard scene, in storyboard order.")
    starts = [m.start_s for m in body.scenes]
    if starts and starts[0] != 0:
        errors.append("The first scene starts the video, at 0 s.")
    if any(b <= a for a, b in itertools.pairwise(starts)):
        errors.append("Each scene must start after the one before it.")
    duration = int(lec.master.get("duration_s") or 0)
    if starts and starts[-1] >= duration:
        errors.append(f"Every scene must start before the end of the master video ({duration} s).")
    if errors:
        raise Unprocessable(
            "These markers don't fit the storyboard and the master video.", errors=errors, scenes=scene_ids
        )
    lec.markers = {"master_sha256": lec.master.get("sha256"), "scenes": [m.model_dump() for m in body.scenes]}
    record(db, actor=who.user.id, action="lecture.markers_set", target_type="lecture", target_id=str(lec.id),
           details={"master_sha256": lec.master.get("sha256"), "scenes": len(body.scenes)})  # fmt: skip
    db.commit()
    db.refresh(lec)
    return _out(db, lec)


@router.put("/lectures/{lecture_id}/captions", response_model=LectureOut, summary="Attach reviewed captions")
def set_captions(db: DB, who: Author, lecture_id: uuid.UUID, body: CaptionIn) -> LectureOut:
    lec = _editable(db, who, lecture_id)
    problems = _caption_problems(db, lec, str(body.asset_version_id))
    if problems:
        raise Unprocessable("These captions can't be attached.", errors=problems)
    lec.captions = {**lec.captions, body.language: str(body.asset_version_id)}
    db.commit()
    db.refresh(lec)
    return _out(db, lec)


@router.post("/lectures/{lecture_id}/submit", response_model=LectureOut, summary="Submit for academic review")
def submit_lecture(db: DB, who: Author, lecture_id: uuid.UUID) -> LectureOut:
    lec = _editable(db, who, lecture_id)
    missing = _missing(db, lec)
    if missing:
        raise Unprocessable("The lecture isn't ready for review.", errors=missing)
    lec.status = "in_review"
    lec.submitted_at = func.now()
    record(db, actor=who.user.id, action="lecture.submitted", target_type="lecture", target_id=str(lec.id))
    db.commit()
    db.refresh(lec)
    return _out(db, lec)


@router.post(
    "/lectures/{lecture_id}/review",
    response_model=LectureOut,
    summary="Independent academic review: approve only with every check passed, or request changes",
)
def review_lecture(db: DB, who: Reviewer, lecture_id: uuid.UUID, body: ReviewIn) -> LectureOut:
    lec = _get(db, who, lecture_id, for_update=True)
    if "subject_reviewer" not in _roles(db, who, lec.grade_number, lec.subject_code):
        raise Forbidden("Only a subject reviewer for this class and subject can review lectures.")
    if str(who.user.id) in lec.contributors:
        raise Forbidden("Someone who produced this lecture can't review it.")
    if lec.status != "in_review":
        raise Conflict("Only a lecture submitted for review can be reviewed.")
    failed = [c for c in CHECKLIST if not body.checklist.get(c)]
    if body.decision == "approve" and failed:
        raise Unprocessable("Approval needs every check passed.", errors=[f"Not checked: {c}" for c in failed])
    lec.review = {
        "decision": body.decision,
        "checklist": {c: bool(body.checklist.get(c)) for c in CHECKLIST},
        "notes": body.notes,
        "reviewer": str(who.user.id),
    }
    if body.decision == "approve":
        lec.status, lec.approved_by, lec.approved_at = "approved", who.user.id, func.now()
    else:
        lec.status = "changes_requested"
    record(db, actor=who.user.id, action=f"lecture.review_{body.decision}", target_type="lecture",
           target_id=str(lec.id))  # fmt: skip
    db.commit()
    db.refresh(lec)
    return _out(db, lec)
