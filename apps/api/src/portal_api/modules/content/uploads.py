"""Resumable master-video uploads (roadmap P07.S2.T1; MEDIA-UPLOAD-01).

A content author uploads a lecture's master video in chunks into the private archive. Storage is the local asset
directory (`PORTAL_ASSET_DIR`) until object storage and the media provider exist (B03, B05); the session/state model is
what the provider adapter will drive later (its callback becomes the `processing` step).

* **Session:** file name, declared size (≤ `MAX_BYTES`), type (MP4, WebM or QuickTime), duration and, optionally, the
  owner's SHA-256 for the file. Only a content author in the lecture's class and subject, while the lecture is still
  being produced, can start one. Sessions expire after `TTL`.
* **Chunks** (≤ `CHUNK_BYTES`) must arrive at the current offset. A chunk ending at or before the received length is a
  retry after a lost response and changes nothing; a gap is refused with the expected offset (`UPLOAD_OFFSET`), which
  is also what `GET` returns, so a dropped connection resumes from the server's count, never from the client's guess.
* **Finishing:** when every byte has arrived the session is committed as `processing`, then the file is checked: a
  video signature, and the SHA-256 against the owner's record when one was given. A good file is archived under its
  hash and becomes the lecture's master (`ready`); otherwise `failed` with the reason and the partial file is removed.
  Upload success is never academic approval: the lecture still needs its independent review (LECTURE-01).
* **Reconciliation** (`portal-upload-reconcile`): expired sessions fail and their partial files are deleted; a session
  stuck in `processing` (a crash mid-check) is checked again.
"""

from __future__ import annotations

import hashlib
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.budget import process_class
from portal_api.db import Base, get_session
from portal_api.errors import Conflict, NotFound, StorageUnavailable, TooLarge, Unprocessable
from portal_api.modules.audit.models import record
from portal_api.modules.identity.deps import Principal, require
from portal_api.modules.identity.permissions import Permission

MAX_BYTES = 8 * 1024 * 1024 * 1024  # 8 GB: a 7-minute 1080x1920 master with headroom
CHUNK_BYTES = 16 * 1024 * 1024
TTL = timedelta(hours=24)
STUCK = timedelta(minutes=15)
TYPES = {"video/mp4": "mp4", "video/webm": "webm", "video/quicktime": "mov"}
STATES = ("uploading", "processing", "ready", "failed")


class MediaUpload(Base):
    __tablename__ = "media_upload"
    __table_args__ = (CheckConstraint(f"state in ({', '.join(repr(s) for s in STATES)})", name="media_upload_state"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lecture_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lecture.id", ondelete="RESTRICT"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(40))
    bytes: Mapped[int] = mapped_column(BigInteger)
    duration_s: Mapped[int] = mapped_column(Integer)
    expected_sha256: Mapped[str | None] = mapped_column(String(64))
    received: Mapped[int] = mapped_column(BigInteger, default=0)
    state: Mapped[str] = mapped_column(String(12), default="uploading")
    failure: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(String(64))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def _dir(name: str) -> Path:
    from portal_api.modules.content.assets import _root

    d = _root() / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _part(upload_id: uuid.UUID) -> Path:
    return _dir("uploads") / f"{upload_id}.part"


def _now(db: Session) -> datetime:
    return db.execute(select(func.now())).scalar_one()


def start(db: Session, who: Principal, lecture_id: uuid.UUID, body: MediaUploadIn) -> MediaUpload:
    from portal_api.modules.content.lectures import _editable

    lec = _editable(db, who, lecture_id)  # an author in scope, while the lecture is still being produced
    up = MediaUpload(
        lecture_id=lec.id,
        filename=body.filename,
        content_type=body.content_type,
        bytes=body.bytes,
        duration_s=body.duration_s,
        expected_sha256=body.sha256,
        created_by=who.user.id,
        expires_at=_now(db) + TTL,
    )
    db.add(up)
    db.flush()
    _part(up.id).write_bytes(b"")
    record(db, actor=who.user.id, action="lecture.master_upload_started", target_type="lecture",
           target_id=str(lec.id), details={"upload_id": str(up.id), "bytes": body.bytes})  # fmt: skip
    db.commit()
    return up


def _mine(db: Session, who: Principal, upload_id: uuid.UUID, *, lock: bool = False) -> MediaUpload:
    from portal_api.modules.content.lectures import _get

    stmt = select(MediaUpload).where(MediaUpload.id == upload_id)
    up = db.scalar(stmt.with_for_update() if lock else stmt)
    if up is None:
        raise NotFound("Upload not found.")
    _get(db, who, up.lecture_id)  # the lecture must be in the caller's scope, or it doesn't exist for them
    return up


def get(db: Session, who: Principal, upload_id: uuid.UUID) -> MediaUpload:
    return _mine(db, who, upload_id)


def write_chunk(db: Session, who: Principal, upload_id: uuid.UUID, offset: int, data: bytes) -> MediaUpload:
    up = _mine(db, who, upload_id, lock=True)
    if up.state != "uploading":
        raise Conflict(
            f"This upload is {up.state}; start a new one to send the file again.", code_reason="UPLOAD_CLOSED"
        )
    if _now(db) >= up.expires_at:
        _fail(db, up, "The upload expired before it finished. Start it again.")
        db.commit()
        raise Conflict("This upload expired. Start a new one.", code_reason="UPLOAD_CLOSED")
    if offset + len(data) <= up.received:
        db.rollback()
        return up  # a retried chunk whose response was lost: already stored
    if offset != up.received:
        raise Conflict(
            "This chunk doesn't continue the upload. Resume from the expected offset.",
            code_reason="UPLOAD_OFFSET",
            expected_offset=up.received,
        )
    if offset + len(data) > up.bytes:
        raise Unprocessable("This is more data than the file size given when the upload started.")
    try:
        with _part(up.id).open("r+b") as f:
            f.seek(offset)
            f.write(data)
            f.truncate()
    except OSError as e:
        db.rollback()  # DEGRADATION-01: the resume point stays where it was; send the same chunk again
        raise StorageUnavailable("We couldn't store this part of the file. Send the same part again shortly.") from e
    up.received = offset + len(data)
    up.updated_at = func.now()
    if up.received < up.bytes:
        db.commit()
        return up
    up.state = "processing"  # committed first: a crash during the check leaves it for the reconciler
    db.commit()
    return finish(db, up.id)


def _signature_ok(path: Path, content_type: str) -> bool:
    with path.open("rb") as f:
        head = f.read(16)
    if content_type in ("video/mp4", "video/quicktime"):
        return head[4:8] == b"ftyp"
    return head[:4] == b"\x1a\x45\xdf\xa3"  # WebM (Matroska/EBML)


def _fail(db: Session, up: MediaUpload, reason: str) -> None:
    up.state, up.failure, up.updated_at = "failed", reason, func.now()
    _part(up.id).unlink(missing_ok=True)


def finish(db: Session, upload_id: uuid.UUID) -> MediaUpload:
    """Check a fully received upload and, if good, make it the lecture's master."""
    from portal_api.modules.content.lectures import Lecture

    up = db.scalar(select(MediaUpload).where(MediaUpload.id == upload_id).with_for_update())
    assert up is not None
    if up.state != "processing":
        db.rollback()
        return up
    path = _part(up.id)
    if not path.exists() or path.stat().st_size != up.bytes:
        _fail(db, up, "The received file is incomplete. Start the upload again.")
    elif not _signature_ok(path, up.content_type):
        _fail(db, up, "This file isn't an MP4, WebM or QuickTime video.")
    else:
        digest = hashlib.sha256()
        with path.open("rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(block)
        sha = digest.hexdigest()
        if up.expected_sha256 and sha != up.expected_sha256:
            _fail(db, up, f"The SHA-256 of the received file ({sha[:12]}…) doesn't match the owner's record.")
        else:
            lec = db.scalar(select(Lecture).where(Lecture.id == up.lecture_id).with_for_update())
            assert lec is not None
            target = _dir(f"masters/{lec.id}") / f"{sha}.{TYPES[up.content_type]}"
            shutil.move(str(path), target)
            up.sha256, up.state, up.updated_at = sha, "ready", func.now()
            lec.master = {
                "filename": up.filename,
                "sha256": sha,
                "bytes": up.bytes,
                "duration_s": up.duration_s,
                "location": "Portal archive (private; moves to the media provider with B05)",
                "upload_id": str(up.id),
            }
            lec.updated_at = func.now()
            details = {"sha256": sha, "bytes": up.bytes, "upload_id": str(up.id)}
            record(db, actor=up.created_by, action="lecture.master_registered", target_type="lecture",
                   target_id=str(lec.id), details=details)  # fmt: skip
    db.commit()
    db.refresh(up)
    return up


def reconcile(db: Session) -> dict[str, int]:
    """Fail expired sessions (removing partial files) and re-check sessions stuck in processing."""
    now = _now(db)
    expired = list(
        db.scalars(select(MediaUpload).where(MediaUpload.state == "uploading", MediaUpload.expires_at <= now))
    )
    for up in expired:
        _fail(db, up, "The upload expired before it finished. Start it again.")
    db.commit()
    stuck = list(
        db.scalars(
            select(MediaUpload.id).where(MediaUpload.state == "processing", MediaUpload.updated_at <= now - STUCK)
        )
    )
    for uid in stuck:
        finish(db, uid)
    return {"expired": len(expired), "rechecked": len(stuck)}


@process_class("bulk")
def main() -> None:  # pragma: no cover - thin CLI wrapper
    """portal-upload-reconcile: the scheduled reconciliation of master-video uploads."""
    from portal_api.budget import bulk_paused_now
    from portal_api.db import get_sessionmaker

    if why := bulk_paused_now():  # POOL-CAPS-01: the next scheduled run does it
        print(f"skipped: {why}", flush=True)
        return

    with get_sessionmaker()() as db:
        print(reconcile(db))


# ------------------------------------------------------------------ routes
router = APIRouter(prefix="/v1/studio", tags=["studio"])
DB = Annotated[Session, Depends(get_session)]
Author = Annotated[Principal, Depends(require(Permission.draft_content))]


class MediaUploadIn(BaseModel):
    filename: str = Field(min_length=3, max_length=255)
    bytes: int = Field(ge=1, le=MAX_BYTES)
    content_type: Literal["video/mp4", "video/webm", "video/quicktime"]
    duration_s: int = Field(ge=1, le=7200)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$", description="The owner's checksum, if known")


class MediaUploadOut(BaseModel):
    id: uuid.UUID
    lecture_id: uuid.UUID
    filename: str
    bytes: int
    received: int
    state: Literal["uploading", "processing", "ready", "failed"]
    failure: str | None
    sha256: str | None
    chunk_bytes: int
    expires_at: datetime


def _out(up: MediaUpload) -> MediaUploadOut:
    return MediaUploadOut(
        id=up.id,
        lecture_id=up.lecture_id,
        filename=up.filename,
        bytes=up.bytes,
        received=up.received,
        state=up.state,  # type: ignore[arg-type]
        failure=up.failure,
        sha256=up.sha256,
        chunk_bytes=CHUNK_BYTES,
        expires_at=up.expires_at,
    )


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


@router.post(
    "/lectures/{lecture_id}/master-upload",
    response_model=MediaUploadOut,
    status_code=201,
    summary="Start a resumable upload of the lecture's master video",
)
def start_upload(db: DB, who: Author, lecture_id: uuid.UUID, body: MediaUploadIn, response: Response) -> MediaUploadOut:
    _private(response)
    return _out(start(db, who, lecture_id, body))


@router.get("/uploads/{upload_id}", response_model=MediaUploadOut, summary="An upload's state and resume offset")
def upload_state(db: DB, who: Author, upload_id: uuid.UUID, response: Response) -> MediaUploadOut:
    _private(response)
    return _out(get(db, who, upload_id))


@router.put(
    "/uploads/{upload_id}", response_model=MediaUploadOut, summary="Send one chunk at the given offset (raw bytes)"
)
async def upload_chunk(
    db: DB,
    who: Author,
    upload_id: uuid.UUID,
    request: Request,
    response: Response,
    offset: Annotated[int, Query(ge=0)],
) -> MediaUploadOut:
    from fastapi.concurrency import run_in_threadpool

    _private(response)
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > CHUNK_BYTES:
        raise TooLarge(f"Send at most {CHUNK_BYTES // (1024 * 1024)} MB per chunk.")
    buf = bytearray()
    async for part in request.stream():
        buf.extend(part)
        if len(buf) > CHUNK_BYTES:
            raise TooLarge(f"Send at most {CHUNK_BYTES // (1024 * 1024)} MB per chunk.")
    if not buf:
        raise Unprocessable("The chunk is empty.")
    return _out(await run_in_threadpool(write_chunk, db, who, upload_id, offset, bytes(buf)))
