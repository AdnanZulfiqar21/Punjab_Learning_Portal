"""Media packs for the asset archive (roadmap P06.S2.T1 media manifests, P07.S2.T4; MEDIA-MANIFEST-01).

A media pack is a zip holding `manifest.json` and the files it lists (see `docs/content-import.md`):

    {"schema_version": 1, "kind": "media", "grade": 11, "subject": "biology",
     "items": [{"external_id": "...", "kind": "image", "title": "...", "file": "figures/cell.png",
                "sha256": "<optional>", "provenance": {"source": "...", "author": "", "licence": "", "tool": ""}}]}

Each entry is an archived asset keyed by `external_id` within the class and subject, so the same pack imported twice
changes nothing and a changed file becomes the asset's next version (versions are immutable; ASSETS-01). Every file is
read with its kind's size cap, checked against its checksum when one is given, scanned and validated exactly as a
single upload is. A **preview** writes nothing. A **commit** re-checks everything and archives all the files in one
transaction, or none when any entry has an error; a failure part-way takes back every file already written.
"""

from __future__ import annotations

import io
import json
import re
import uuid
import zipfile
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from portal_api.errors import Conflict, Forbidden, TooLarge, Unprocessable
from portal_api.modules.audit.models import record
from portal_api.modules.content import assets
from portal_api.modules.identity.deps import Principal

SCHEMA_VERSION = 1
MAX_PACK_BYTES = 60 * 1024 * 1024
MAX_ITEMS = 200
MAX_MANIFEST_BYTES = 1024 * 1024
EXTERNAL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$")
TITLE_MAX = 200


@dataclass
class Entry:
    external_id: str
    kind: str
    file: str
    title: str
    action: str = "create"  # create | version | unchanged | error
    errors: list[str] = field(default_factory=list)
    sha256: str | None = None
    size: int | None = None
    asset_id: uuid.UUID | None = None
    version_id: uuid.UUID | None = None
    number: int | None = None
    data: bytes | None = field(default=None, repr=False)
    derived: dict[str, Any] | None = field(default=None, repr=False)
    provenance: dict[str, str] = field(default_factory=dict)


@dataclass
class Pack:
    grade: int
    subject: str
    entries: list[Entry]
    committed: bool = False

    @property
    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for e in self.entries:
            out[e.action] = out.get(e.action, 0) + 1
        return out


def _bad(message: str, reason: str = "MEDIA_PACK") -> Unprocessable:
    return Unprocessable(message, code_reason=reason)


def _manifest(z: zipfile.ZipFile) -> dict[str, Any]:
    from portal_api.modules.content.imports import _check_shape

    try:
        with z.open("manifest.json") as f:
            raw = f.read(MAX_MANIFEST_BYTES + 1)
    except KeyError:
        raise _bad("The pack has no manifest.json at its top level.") from None
    if len(raw) > MAX_MANIFEST_BYTES:
        raise TooLarge("manifest.json can be at most 1 MB.")
    try:
        doc = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        raise _bad("manifest.json is not valid UTF-8 JSON.") from None
    _check_shape(doc)
    if not isinstance(doc, dict) or doc.get("kind") != "media":
        raise _bad('manifest.json must be an object with "kind": "media".')
    if doc.get("schema_version") != SCHEMA_VERSION:
        raise _bad(f"Unsupported schema_version; this portal reads version {SCHEMA_VERSION}.", "SCHEMA_VERSION")
    if doc.get("grade") not in (11, 12) or not isinstance(doc.get("subject"), str):
        raise _bad("manifest.json must give the class (grade 11 or 12) and the subject code.")
    items = doc.get("items")
    if not isinstance(items, list) or not items:
        raise _bad("manifest.json lists no items.")
    if len(items) > MAX_ITEMS:
        raise TooLarge(f"A pack can list at most {MAX_ITEMS} files; split it.")
    return doc


def _read_member(z: zipfile.ZipFile, name: str, limit: int) -> bytes | str:
    """The member's bytes, or why it can't be used. Names are matched exactly; nothing outside the pack is reachable."""
    if not name or name.startswith(("/", "\\")) or "\\" in name or ".." in name.split("/") or name == "manifest.json":
        return "The file name must be a plain path inside the pack."
    try:
        with z.open(name) as f:
            data = f.read(limit + 1)
    except KeyError:
        return f"{name} is not in the pack."
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError):
        return f"{name} can't be unpacked (encrypted or an unsupported compression)."
    if len(data) > limit:
        return f"{name} is larger than {limit // (1024 * 1024)} MB."
    if not data:
        return f"{name} is empty."
    return data


def _check(db: Session, z: zipfile.ZipFile, grade: int, subject: str, raw_items: list[Any]) -> list[Entry]:
    from portal_api.modules.system import scanning

    entries: list[Entry] = []
    seen: set[str] = set()
    for raw in raw_items:
        item = raw if isinstance(raw, dict) else {}
        e = Entry(
            external_id=str(item.get("external_id") or "")[:120],
            kind=str(item.get("kind") or "")[:20],
            file=str(item.get("file") or "")[:300],
            title=str(item.get("title") or "").strip()[:TITLE_MAX],
        )
        entries.append(e)
        given = item.get("provenance")
        prov: dict[str, Any] = given if isinstance(given, dict) else {}
        e.provenance = {k: str(prov.get(k) or "")[:500] for k in ("source", "author", "licence", "tool")}
        if not EXTERNAL_ID.match(e.external_id):
            e.errors.append("external_id must be 1-120 letters, digits, '.', '_', ':' or '-'.")
        elif e.external_id in seen:
            e.errors.append("This external_id is already used earlier in the pack.")
        seen.add(e.external_id)
        if e.kind not in assets.KINDS:
            e.errors.append(f"kind must be one of: {', '.join(assets.KINDS)}.")
        if not e.title:
            e.errors.append("Give the file a title.")
        if not e.provenance["source"].strip():
            e.errors.append("Say where this file comes from (provenance.source).")
        expected = item.get("sha256")
        if expected is not None and not (isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected)):
            e.errors.append("sha256, when given, must be 64 lowercase hex characters.")
            expected = None
        if e.errors:
            e.action = "error"
            continue
        got = _read_member(z, e.file, assets.MAX_BYTES[e.kind])
        if isinstance(got, str):
            e.errors.append(got)
            e.action = "error"
            continue
        e.data, e.size, e.sha256 = got, len(got), assets._sha(got)
        if expected and expected != e.sha256:
            e.errors.append("The file doesn't match its sha256; it may be damaged or a different file.")
            e.action = "error"
            continue
        existing = db.scalar(
            select(assets.Asset).where(
                assets.Asset.grade_number == grade,
                assets.Asset.subject_code == subject,
                assets.Asset.external_ref == e.external_id,
            )
        )
        if existing is not None:
            e.asset_id = existing.id
            if existing.kind != e.kind:
                e.errors.append(f"This external_id is already a {existing.kind}; it can't become a {e.kind}.")
                e.action = "error"
                continue
            latest = db.scalar(
                select(assets.AssetVersion)
                .where(assets.AssetVersion.asset_id == existing.id)
                .order_by(assets.AssetVersion.number.desc())
                .limit(1)
            )
            if latest is not None and latest.master_sha256 == e.sha256:
                e.action, e.version_id, e.number = "unchanged", latest.id, latest.number
                e.data = None
                continue
            e.action = "version"
        try:  # a scanner outage (503) stops the whole pack; it never skips a file
            scanning.require_clean(e.data)
            e.derived = assets._derive(e.kind, e.data)
        except Unprocessable as err:
            e.errors.append(err.detail)
            e.action = "error"
    return entries


def run(db: Session, who: Principal, data: bytes, *, commit: bool) -> Pack:
    from portal_api.modules.content.workflow import roles_in_scope

    if len(data) > MAX_PACK_BYTES:
        raise TooLarge(f"A media pack can be at most {MAX_PACK_BYTES // (1024 * 1024)} MB; split it.")
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise _bad("A media pack must be a .zip file holding manifest.json and the files it lists.") from None
    with z:
        if len(z.infolist()) > MAX_ITEMS + 50:
            raise TooLarge(f"A pack can hold at most {MAX_ITEMS} files; split it.")
        doc = _manifest(z)
        grade, subject = int(doc["grade"]), str(doc["subject"])
        held = {r.value for r in roles_in_scope(db, who.user.id, grade, subject)}
        if "content_author" not in held:
            raise Forbidden("Only content authors for this class and subject can add its media.")
        pack = Pack(grade=grade, subject=subject, entries=_check(db, z, grade, subject, doc["items"]))
    db.commit()  # end the read transaction; nothing slow happens under a lock
    if not commit:
        return pack
    if any(e.action == "error" for e in pack.entries):
        raise Unprocessable("Fix the errors shown in the preview, then import the pack again.",
                            code_reason="MANIFEST_ERRORS")  # fmt: skip
    _write_all(db, who, pack)
    return pack


def _write_all(db: Session, who: Principal, pack: Pack) -> None:
    written: list[str] = []
    try:
        for e in pack.entries:
            if e.action == "unchanged":
                continue
            assert e.data is not None and e.derived is not None
            if e.action == "create":
                asset = assets.Asset(
                    kind=e.kind,
                    title=e.title,
                    grade_number=pack.grade,
                    subject_code=pack.subject,
                    external_ref=e.external_id,
                    created_by=who.user.id,
                )
                db.add(asset)
                db.flush()  # the unique key stops two packs racing to create the same external_id
                record(db, actor=who.user.id, action="asset.created", target_type="content_asset",
                       target_id=str(asset.id), details={"kind": e.kind, "external_id": e.external_id})  # fmt: skip
            else:
                locked = db.scalar(select(assets.Asset).where(assets.Asset.id == e.asset_id).with_for_update())
                if locked is None:
                    raise Conflict("An asset in this pack changed while it was checked; preview the pack again.")
                asset = locked
                latest = db.scalar(
                    select(assets.AssetVersion.master_sha256)
                    .where(assets.AssetVersion.asset_id == asset.id)
                    .order_by(assets.AssetVersion.number.desc())
                    .limit(1)
                )
                if latest == e.sha256:  # another import archived this same file meanwhile
                    e.action = "unchanged"
                    continue
            version = assets.new_version(db, who, asset, e.data, e.derived, e.provenance, written)
            e.asset_id, e.version_id, e.number = asset.id, version.id, version.number
        record(db, actor=who.user.id, action="asset.media_pack_imported", target_type="content_asset",
               target_id=f"{pack.grade}:{pack.subject}", details=pack.counts)  # fmt: skip
        db.commit()
    except IntegrityError:
        db.rollback()
        assets.remove_files(written)
        raise Conflict("Another import added one of these files meanwhile; preview the pack again.") from None
    except BaseException:
        db.rollback()  # all or nothing: no version row, and no file left without one
        assets.remove_files(written)
        raise
    pack.committed = True
