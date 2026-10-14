"""P06.S2.T1 (MEDIA-MANIFEST-01): media packs for the asset archive.

A media pack is a zip holding `manifest.json` and the files it lists. Each entry has a stable `external_id`, so the
same pack imported twice changes nothing, and a changed file becomes the asset's next version (never an overwrite).
A preview scans and validates every file and writes nothing; a commit re-checks everything and archives every file
in one transaction, or none when any entry has an error. Only content authors in the pack's class and subject can
import it. Synthetic fixture files only.
"""

from __future__ import annotations

import hashlib
import io
import json
import uuid
import zipfile
from typing import Any

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from portal_api.modules.content import assets
from tests.test_content_workflow import Staff
from tests.test_evidence import _pdf

BIO = {"grades": [11], "subjects": ["biology"]}
SRC = {"source": "Fixture: drawn by the test suite", "licence": "Owner's own work"}
CAPTION = b"WEBVTT\n\n00:00.000 --> 00:02.000\nFixture caption\n"


def _png(colour: tuple[int, int, int] = (10, 120, 200)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 6), colour).save(buf, format="PNG")
    return buf.getvalue()


def _pack(items: list[dict[str, Any]], files: dict[str, bytes], **head: Any) -> bytes:
    manifest = {"schema_version": 1, "kind": "media", "grade": 11, "subject": "biology", "items": items, **head}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest))
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


def _item(ext: str, kind: str, file: str, **extra: Any) -> dict[str, Any]:
    return {
        "external_id": ext,
        "kind": kind,
        "title": f"Fixture {kind} {ext}",
        "file": file,
        "provenance": SRC,
        **extra,
    }


def _send(client: TestClient, who: Staff, data: bytes, *, commit: bool = False) -> Any:
    return client.post(
        "/v1/studio/assets/manifest",
        params={"commit": str(commit).lower()},
        headers={**who.headers, "Content-Type": "application/octet-stream"},
        content=data,
    )


def _versions(external_ref: str) -> int:
    with get_sessionmaker()() as db:
        return int(
            db.scalar(
                select(func.count(assets.AssetVersion.id))
                .join(assets.Asset, assets.Asset.id == assets.AssetVersion.asset_id)
                .where(assets.Asset.external_ref == external_ref)
            )
            or 0
        )


def test_a_media_pack_previews_then_archives_every_file_once(client: TestClient, db: Session) -> None:
    author = Staff(client, db, ["content_author"], BIO)
    run = uuid.uuid4().hex[:8]
    png, pdf = _png(), _pdf(2)
    items = [
        _item(f"fig-{run}", "image", "figures/cell.png", sha256=hashlib.sha256(png).hexdigest()),
        _item(f"handout-{run}", "handout", "handout.pdf"),
        _item(f"cap-{run}", "caption", "captions/intro.vtt"),
    ]
    pack = _pack(items, {"figures/cell.png": png, "handout.pdf": pdf, "captions/intro.vtt": CAPTION})

    preview = _send(client, author, pack)
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["committed"] is False and body["counts"] == {"create": 3}, body["entries"]
    assert (body["grade"], body["subject"]) == (11, "biology")
    assert _versions(f"fig-{run}") == 0  # a preview writes nothing

    done = _send(client, author, pack, commit=True)
    assert done.status_code == 200, done.text
    out = done.json()
    assert out["committed"] is True and out["counts"] == {"create": 3}
    fig = next(e for e in out["entries"] if e["external_id"] == f"fig-{run}")
    assert fig["number"] == 1 and fig["version_id"] and fig["sha256"] == hashlib.sha256(png).hexdigest()
    detail = client.get(f"/v1/studio/assets/{fig['asset_id']}", headers=author.headers).json()
    assert detail["external_id"] == f"fig-{run}" and detail["title"] == f"Fixture image fig-{run}"
    assert detail["versions"][0]["provenance"]["licence"] == "Owner's own work"
    assert detail["versions"][0]["delivery_state"] == "ready"
    handout = next(e for e in out["entries"] if e["external_id"] == f"handout-{run}")
    assert (
        client.get(f"/v1/studio/assets/{handout['asset_id']}", headers=author.headers).json()["versions"][0]["pages"]
        == 2
    )

    again = _send(client, author, pack, commit=True).json()
    assert again["counts"] == {"unchanged": 3} and _versions(f"fig-{run}") == 1  # idempotent

    files = {"cell.png": _png((200, 30, 30)), "handout.pdf": pdf, "captions/intro.vtt": CAPTION}
    changed = _pack([*items[1:], _item(f"fig-{run}", "image", "cell.png")], files)
    p = _send(client, author, changed).json()
    assert p["counts"] == {"unchanged": 2, "version": 1}, p["entries"]
    v = _send(client, author, changed, commit=True).json()
    fig2 = next(e for e in v["entries"] if e["external_id"] == f"fig-{run}")
    assert fig2["action"] == "version" and fig2["number"] == 2 and fig2["asset_id"] == fig["asset_id"]
    assert _versions(f"fig-{run}") == 2  # version 1 is kept, unchanged


def test_a_pack_with_any_error_archives_nothing(client: TestClient, db: Session) -> None:
    author = Staff(client, db, ["content_author"], BIO)
    run = uuid.uuid4().hex[:8]
    existing = _pack([_item(f"cap-{run}", "caption", "c.vtt")], {"c.vtt": CAPTION})
    assert _send(client, author, existing, commit=True).json()["committed"] is True

    png = _png()
    items = [
        _item(f"good-{run}", "image", "good.png"),
        _item(f"bad-caption-{run}", "caption", "bad.vtt"),
        _item(f"missing-{run}", "image", "nowhere.png"),
        _item(f"checksum-{run}", "image", "good.png", sha256="0" * 64),
        _item(f"good-{run}", "image", "good.png"),  # the same external_id twice
        _item(f"cap-{run}", "image", "good.png"),  # an existing caption can't become an image
        _item(f"escape-{run}", "image", "../good.png"),
        {"external_id": f"noprov-{run}", "kind": "image", "title": "Fixture", "file": "good.png", "provenance": {}},
        _item(f"kind-{run}", "video", "good.png"),
    ]
    pack = _pack(items, {"good.png": png, "bad.vtt": b"not a caption"})
    preview = _send(client, author, pack).json()
    by_id: dict[str, list[str]] = {}
    for e in preview["entries"]:
        by_id.setdefault(e["external_id"], []).append(e["action"])
    assert by_id[f"good-{run}"] == ["create", "error"]
    for ext in ("bad-caption", "missing", "checksum", "cap", "escape", "noprov", "kind"):
        assert by_id[f"{ext}-{run}"] == ["error"], (ext, preview["entries"])
    assert all(e["errors"] for e in preview["entries"] if e["action"] == "error")

    refused = _send(client, author, pack, commit=True)
    assert refused.status_code == 422 and refused.json()["code_reason"] == "MANIFEST_ERRORS"
    assert _versions(f"good-{run}") == 0 and _versions(f"cap-{run}") == 1  # nothing was archived


def test_unsafe_packs_and_people_outside_the_scope_are_refused(client: TestClient, db: Session) -> None:
    author = Staff(client, db, ["content_author"], BIO)
    run = uuid.uuid4().hex[:8]
    png = _png()
    ok = _pack([_item(f"fig-{run}", "image", "a.png")], {"a.png": png})

    def reason(data: bytes, who: Staff = author) -> tuple[int, str | None]:
        r = _send(client, who, data)
        return r.status_code, r.json().get("code_reason")

    assert reason(b"not a zip at all") == (422, "MEDIA_PACK")
    no_manifest = io.BytesIO()
    with zipfile.ZipFile(no_manifest, "w") as z:
        z.writestr("a.png", png)
    assert reason(no_manifest.getvalue()) == (422, "MEDIA_PACK")
    assert reason(_pack([], {})) == (422, "MEDIA_PACK")  # no items
    assert reason(_pack([_item("x", "image", "a.png")], {"a.png": png}, schema_version=2))[1] == "SCHEMA_VERSION"
    huge = _pack([_item(f"big-{run}", "image", "big.png")], {"big.png": b"\0" * (assets.MAX_BYTES["image"] + 1)})
    assert len(huge) < 100_000  # zeros compress well; the unpacked size is what is checked
    big = _send(client, author, huge).json()
    assert big["entries"][0]["action"] == "error" and "MB" in big["entries"][0]["errors"][0]

    physics = Staff(client, db, ["content_author"], {"grades": [12], "subjects": ["physics"]})
    reviewer = Staff(client, db, ["subject_reviewer"], BIO)
    assert reason(ok, physics)[0] == 403  # not this class and subject
    assert reason(ok, reviewer)[0] == 403  # reviewers don't add media
    assert client.post("/v1/studio/assets/manifest", content=ok).status_code == 401
    assert _versions(f"fig-{run}") == 0


def test_a_storage_failure_part_way_leaves_no_version_and_no_file(
    client: TestClient, db: Session, monkeypatch: Any
) -> None:
    author = Staff(client, db, ["content_author"], BIO)
    run = uuid.uuid4().hex[:8]
    items = [_item(f"one-{run}", "image", "1.png"), _item(f"two-{run}", "image", "2.png")]
    pack = _pack(items, {"1.png": _png((1, 2, 3)), "2.png": _png((4, 5, 6))})
    real_write, calls = assets._write, []

    def failing_write(key: str, data: bytes) -> None:
        calls.append(key)
        if len(calls) == 3:  # the second file's master: the first file is already fully written
            raise assets.StorageUnavailable()
        real_write(key, data)

    monkeypatch.setattr(assets, "_write", failing_write)
    r = _send(client, author, pack, commit=True)
    assert r.status_code == 503, r.text
    assert _versions(f"one-{run}") == 0 and _versions(f"two-{run}") == 0
    with get_sessionmaker()() as s:
        assert s.scalar(select(assets.Asset).where(assets.Asset.external_ref == f"one-{run}")) is None
    assert len(calls) == 3 and not any((assets._root() / key).exists() for key in calls)  # every file taken back

    monkeypatch.setattr(assets, "_write", real_write)
    assert _send(client, author, pack, commit=True).json()["counts"] == {"create": 2}  # a retry works
