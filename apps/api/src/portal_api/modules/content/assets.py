"""Owned master archive for content assets (roadmap P07.S2.T4; ASSETS-01).

Diagrams, handouts, captions and diagram sources are archived as **assets** with immutable, numbered **versions**.
Every version keeps its uploaded master privately with its checksum and provenance (who made it, from what, under
which licence). A **delivery copy** is derived from the master in the isolated evidence worker: images are re-encoded
to PNG (no metadata, no embedded content), PDF handouts are validated page by page and kept as uploaded, captions must
be UTF-8 WebVTT. Diagram sources (e.g. SVG, editable files) are archived but never served, because they can carry
script. Every upload is scanned first (UPLOAD-SCAN-01).

Content refers to an asset *version* by its ID (for example a fallback's `image_asset_id`), so a published lesson keeps
showing exactly what was reviewed. **Retention:** masters are never deleted. The scheduled collection job only purges
the delivery copy of a superseded version that no content version refers to and that is older than the retention
period; an admin can re-derive it from the master at any time. Both are audited.

Storage is a private local directory (`PORTAL_ASSET_DIR`) until the media provider and object storage exist (B03, B05).
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.db import Base
from portal_api.errors import Forbidden, NotFound, TooLarge, Unprocessable
from portal_api.modules.audit.models import record
from portal_api.modules.identity.deps import Principal

KINDS = ("image", "handout", "caption", "diagram_source")
SERVED = {"image", "handout", "caption"}  # diagram sources are archived, never served
MAX_BYTES = {
    "image": 8 * 1024 * 1024,
    "handout": 20 * 1024 * 1024,
    "caption": 1024 * 1024,
    "diagram_source": 20 * 1024 * 1024,
}
RETENTION = timedelta(days=30)


class Asset(Base):
    __tablename__ = "content_asset"
    __table_args__ = (
        CheckConstraint("kind in ('image','handout','caption','diagram_source')", name="content_asset_kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(Text)
    grade_number: Mapped[int] = mapped_column(SmallInteger)
    subject_code: Mapped[str] = mapped_column(String(40))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AssetVersion(Base):
    __tablename__ = "content_asset_version"
    __table_args__ = (
        UniqueConstraint("asset_id", "number", name="uq_content_asset_version_number"),
        CheckConstraint("delivery_state in ('ready','none','purged')", name="content_asset_version_delivery"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_asset.id", ondelete="RESTRICT"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    master_key: Mapped[str] = mapped_column(Text)
    master_sha256: Mapped[str] = mapped_column(String(64))
    master_bytes: Mapped[int] = mapped_column(Integer)
    media_type: Mapped[str] = mapped_column(String(60))
    delivery_key: Mapped[str | None] = mapped_column(Text)
    delivery_sha256: Mapped[str | None] = mapped_column(String(64))
    delivery_media_type: Mapped[str | None] = mapped_column(String(60))
    delivery_state: Mapped[str] = mapped_column(String(8))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    pages: Mapped[int | None] = mapped_column(Integer)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ------------------------------------------------------------------ storage
def _root() -> Path:
    from portal_api.config import get_settings

    base = Path(os.environ.get("PORTAL_ASSET_DIR") or Path(get_settings().evidence_dir).parent / "assets")
    if not base.is_absolute():
        base = Path(__file__).resolve().parents[4] / base
    base.mkdir(parents=True, exist_ok=True)
    return base


def _write(key: str, data: bytes) -> None:
    path = _root() / key
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(data)
    tmp.replace(path)  # atomic: a reader never sees half a file


def read(key: str) -> bytes:
    return (_root() / key).read_bytes()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ------------------------------------------------------------------ access
def _require_role(db: Session, who: Principal, asset: Asset, roles: set[str], *, mfa: bool = False) -> None:
    from portal_api.modules.content.workflow import roles_in_scope

    held = {r.value for r in roles_in_scope(db, who.user.id, asset.grade_number, asset.subject_code)}
    if not held & roles:
        raise NotFound("Asset not found.")  # don't reveal assets outside the caller's scope
    if mfa and not who.claims.mfa:
        raise Forbidden("This needs a multi-factor authenticated session. Sign in again with MFA.")


STAFF = {"content_author", "subject_reviewer", "publisher", "academic_adjudicator"}


def get_asset(db: Session, who: Principal, asset_id: uuid.UUID) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise NotFound("Asset not found.")
    _require_role(db, who, asset, STAFF)
    return asset


def get_version(db: Session, who: Principal, version_id: uuid.UUID) -> tuple[Asset, AssetVersion]:
    version = db.get(AssetVersion, version_id)
    if version is None:
        raise NotFound("Asset not found.")
    return get_asset(db, who, version.asset_id), version


# ------------------------------------------------------------------ create and upload
def create(db: Session, who: Principal, *, kind: str, title: str, grade: int, subject: str) -> Asset:
    if kind not in KINDS:
        raise Unprocessable(f"kind must be one of: {', '.join(KINDS)}.")
    asset = Asset(kind=kind, title=title.strip(), grade_number=grade, subject_code=subject, created_by=who.user.id)
    _require_role(db, who, asset, {"content_author"})
    db.add(asset)
    db.flush()
    record(db, actor=who.user.id, action="asset.created", target_type="content_asset", target_id=str(asset.id),
           details={"kind": kind})  # fmt: skip
    db.commit()
    return asset


def _derive(kind: str, data: bytes) -> dict[str, Any]:
    """Validate the master and derive the delivery copy (isolated worker for images and PDFs)."""
    from portal_api.modules.written import evidence

    if kind == "caption":
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            raise Unprocessable("Captions must be UTF-8 WebVTT.", code_reason="ASSET_INVALID") from None
        if not text.lstrip("﻿").startswith("WEBVTT") or "\x00" in text:
            raise Unprocessable("Captions must be a WebVTT file starting with WEBVTT.", code_reason="ASSET_INVALID")
        return {"media_type": "text/vtt", "delivery": data, "delivery_type": "text/vtt"}
    if kind == "diagram_source":
        return {"media_type": "application/octet-stream", "delivery": None, "delivery_type": None}
    try:
        inspected = evidence.inspect(data)
    except evidence.Rejected as e:
        raise Unprocessable(e.reason, code_reason="ASSET_INVALID") from None
    if kind == "image":
        if inspected.content_type == "application/pdf":
            raise Unprocessable("An image asset must be a PNG or JPEG.", code_reason="ASSET_INVALID")
        detail = evidence.render_detail(data, inspected.content_type, 0, None)  # a fresh PNG: no metadata
        return {
            "media_type": inspected.content_type,
            "delivery": detail.png,
            "delivery_type": "image/png",
            "width": detail.width,
            "height": detail.height,
        }
    if inspected.content_type != "application/pdf":
        raise Unprocessable("A handout must be a PDF.", code_reason="ASSET_INVALID")
    return {
        "media_type": "application/pdf",
        "delivery": data,
        "delivery_type": "application/pdf",
        "pages": len(inspected.pages),
    }


def upload(db: Session, who: Principal, asset_id: uuid.UUID, data: bytes, provenance: dict[str, Any]) -> AssetVersion:
    from portal_api.modules.system import scanning

    asset = db.get(Asset, asset_id)
    if asset is None:
        raise NotFound("Asset not found.")
    _require_role(db, who, asset, {"content_author"})
    if not data:
        raise Unprocessable("The file is empty.", code_reason="ASSET_INVALID")
    if len(data) > MAX_BYTES[asset.kind]:
        raise TooLarge(f"A {asset.kind} can be at most {MAX_BYTES[asset.kind] // (1024 * 1024)} MB.")
    if not str(provenance.get("source", "")).strip():
        raise Unprocessable("Say where this file comes from (who made it, from what).", code_reason="PROVENANCE")
    scanning.require_clean(data)
    derived = _derive(asset.kind, data)
    db.commit()  # nothing slow happens under a lock: derive first, then number the version
    asset = db.scalar(select(Asset).where(Asset.id == asset_id).with_for_update())
    assert asset is not None
    number = (db.scalar(select(func.max(AssetVersion.number)).where(AssetVersion.asset_id == asset.id)) or 0) + 1
    version = AssetVersion(id=uuid.uuid4(), asset_id=asset.id, number=number)
    version.master_key = f"{asset.id}/{version.id}/master"
    version.master_sha256 = _sha(data)
    version.master_bytes = len(data)
    version.media_type = derived["media_type"]
    version.width, version.height, version.pages = derived.get("width"), derived.get("height"), derived.get("pages")
    version.provenance = {
        k: str(v)[:500] for k, v in provenance.items() if k in ("source", "author", "licence", "tool")
    }
    version.created_by = who.user.id
    _write(version.master_key, data)
    _set_delivery(version, derived["delivery"], derived["delivery_type"])
    db.add(version)
    record(db, actor=who.user.id, action="asset.version_uploaded", target_type="content_asset_version",
           target_id=str(version.id), details={"number": number, "sha256": version.master_sha256})  # fmt: skip
    db.commit()
    return version


def _set_delivery(version: AssetVersion, data: bytes | None, media_type: str | None) -> None:
    if data is None:
        version.delivery_key = version.delivery_sha256 = version.delivery_media_type = None
        version.delivery_state = "none"
        return
    version.delivery_key = f"{version.asset_id}/{version.id}/delivery"
    _write(version.delivery_key, data)
    version.delivery_sha256 = _sha(data)
    version.delivery_media_type = media_type
    version.delivery_state = "ready"


def rederive(db: Session, who: Principal, version_id: uuid.UUID) -> AssetVersion:
    """Re-ingest the delivery copy from the archived master (after a purge, or a corrupted copy). Audited."""
    asset, version = get_version(db, who, version_id)
    _require_role(db, who, asset, {"publisher"}, mfa=True)
    master = read(version.master_key)
    if _sha(master) != version.master_sha256:
        raise Unprocessable(
            "The archived master doesn't match its checksum; restore it from backup.", code_reason="MASTER_CORRUPT"
        )
    derived = _derive(asset.kind, master)
    _set_delivery(version, derived["delivery"], derived["delivery_type"])
    version.purged_at = None
    record(db, actor=who.user.id, action="asset.delivery_rederived", target_type="content_asset_version",
           target_id=str(version.id))  # fmt: skip
    db.commit()
    return version


# ------------------------------------------------------------------ references and retention
def referenced(db: Session, version_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    """Asset versions that any content version (draft, published or superseded) names. Content versions are never
    deleted and attempts pin content versions, so this covers retained attempts and published lessons."""
    from sqlalchemy import Text as SAText
    from sqlalchemy import cast, or_

    from portal_api.modules.content.models import ContentVersion

    if not version_ids:
        return set()
    out = set()
    for vid in version_ids:
        hit = db.scalar(
            select(ContentVersion.id).where(or_(cast(ContentVersion.body, SAText).contains(str(vid)))).limit(1)
        )
        if hit is not None:
            out.add(vid)
    return out


def collect(db: Session, *, apply: bool, actor: uuid.UUID | None = None, now: datetime | None = None) -> list[str]:
    """Purge delivery copies of superseded, unreferenced versions older than RETENTION. Masters are kept."""
    now = now or db.scalar(select(func.now()))
    assert now is not None
    latest = select(AssetVersion.asset_id, func.max(AssetVersion.number).label("n")).group_by(AssetVersion.asset_id)
    latest_map = {a: n for a, n in db.execute(latest).all()}
    candidates = [
        v
        for v in db.scalars(
            select(AssetVersion).where(
                AssetVersion.delivery_state == "ready", AssetVersion.created_at < now - RETENTION
            )
        )
        if v.number < latest_map.get(v.asset_id, 0)
    ]
    keep = referenced(db, [v.id for v in candidates])
    purged = []
    for v in candidates:
        if v.id in keep:
            continue
        purged.append(str(v.id))
        if apply:
            if v.delivery_key:
                with contextlib.suppress(OSError):
                    (_root() / v.delivery_key).unlink(missing_ok=True)
            v.delivery_key = v.delivery_sha256 = None
            v.delivery_state = "purged"
            v.purged_at = now
            record(db, actor=actor, action="asset.delivery_purged", target_type="content_asset_version",
                   target_id=str(v.id), details={"reason": "superseded, unreferenced, past retention"})  # fmt: skip
    if apply:
        db.commit()
    return purged


def resolve(db: Session, version_id: str) -> AssetVersion | None:
    try:
        return db.get(AssetVersion, uuid.UUID(version_id))
    except ValueError:
        return None


def image_ready(db: Session, version_id: str) -> bool:
    """Whether a reference names an image version whose delivery copy is ready (for fallbacks and diagrams)."""
    v = resolve(db, version_id)
    if v is None or v.delivery_state != "ready":
        return False
    asset = db.get(Asset, v.asset_id)
    return asset is not None and asset.kind == "image"


def main() -> None:  # pragma: no cover - thin CLI wrapper
    """portal-asset-retention [--apply]: the scheduled retention job (dry run by default)."""
    import sys

    from portal_api.db import get_sessionmaker

    with get_sessionmaker()() as db:
        purged = collect(db, apply="--apply" in sys.argv)
    print(("purged " if "--apply" in sys.argv else "would purge ") + f"{len(purged)} delivery copies")


# ------------------------------------------------------------------ references from content (P07.S1.T1)
REF_KIND = {"diagram": "image", "handout": "handout"}
_KIND_NAME = {"image": "an image", "handout": "a PDF handout"}
_CLASS = {11: "Class XI", 12: "Class XII"}


def block_refs(body: object) -> list[tuple[str, str, str]]:
    """(where, asset version ID, required kind) for every diagram, handout and fallback image in a body."""
    out: list[tuple[str, str, str]] = []
    stack: list[object] = [body]
    while stack:  # iterative: bodies are shallow, but never trust their depth
        node = stack.pop()
        if isinstance(node, list):
            stack.extend(node)
        elif isinstance(node, dict):
            kind = node.get("type")
            if isinstance(kind, str) and kind in REF_KIND and isinstance(node.get("asset_version_id"), str):
                out.append((f"{kind} block", node["asset_version_id"], REF_KIND[kind]))
            fb = node.get("fallback")
            if isinstance(fb, dict) and isinstance(fb.get("image_asset_id"), str):
                out.append((f"{kind} fallback", fb["image_asset_id"], "image"))
            stack.extend(v for k, v in node.items() if k != "fallback")
    return out


def check_references(db: Session, grade: int, subject: str, body: object) -> list[str]:
    """Every archived asset a body names must exist, be the right kind, have a ready delivery copy and belong to the
    same class and subject as the content: Class XI and XII material is never mixed."""
    problems = []
    for where, vid, kind in block_refs(body):
        v = resolve(db, vid)
        asset = db.get(Asset, v.asset_id) if v is not None else None
        if v is None or asset is None:
            problems.append(f"The {where} names asset version {vid}, which isn't in the asset archive.")
            continue
        if asset.kind != kind:
            problems.append(f"The {where} names '{asset.title}', which isn't {_KIND_NAME[kind]} ({asset.kind}).")
        if (asset.grade_number, asset.subject_code) != (grade, subject):
            problems.append(
                f"The {where} names '{asset.title}' from {_CLASS.get(asset.grade_number, asset.grade_number)} "
                f"{asset.subject_code}; Class XI and XII (and different subjects) are never mixed."
            )
        if v.delivery_state != "ready":
            problems.append(f"The {where} names '{asset.title}' version {v.number}, which has no delivery copy.")
    return problems


def for_lesson(db: Session, item: Any, version_id: uuid.UUID) -> tuple[AssetVersion, Asset]:
    """The asset version a live lesson's *published* version names, or NotFound. Nothing else in the archive is ever
    reachable by learners."""
    published = item.published
    named = {vid for _, vid, _ in block_refs(published.body)} if published is not None else set()
    v = db.get(AssetVersion, version_id) if str(version_id) in named else None
    asset = db.get(Asset, v.asset_id) if v is not None else None
    if (
        v is None
        or asset is None
        or asset.kind not in SERVED
        or v.delivery_state != "ready"
        or not v.delivery_key
        or (asset.grade_number, asset.subject_code) != (item.grade_number, item.subject_code)
    ):
        raise NotFound("File not found.")
    return v, asset
