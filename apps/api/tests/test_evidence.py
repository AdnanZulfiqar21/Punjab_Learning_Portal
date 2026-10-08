"""Upload evidence validation and logical pages (review R01/R02; W03.S1.T3, W03.S3.T2, §20.8).

All files are synthetic technical fixtures built with real encoders (Pillow, pypdf) or deliberately malformed bytes.
None is a learner script, and nothing here measures marking.
"""

from __future__ import annotations

import io
import os
import struct
import warnings
import zlib
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image, PngImagePlugin
from pypdf import PdfWriter
from sqlalchemy import text

from portal_api.db import get_sessionmaker
from portal_api.modules.written import evidence, service, storage
from tests.test_written_attempts import _learner, _map, _pdf, _png, _seal, _start, _upload


# ------------------------------------------------------------------ fixtures
def _png_header_only() -> bytes:
    ihdr = struct.pack(">IIBBBBB", 1000, 1000, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + ihdr


def _pdf_object_streams() -> bytes:
    """A valid one-page PDF whose objects live in a compressed object stream with a cross-reference stream."""
    objs = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >>",
    }
    header, body = b"", b""
    for n, o in objs.items():
        header += b"%d %d " % (n, len(body))
        body += o + b"\n"
    stream = zlib.compress(header + body)
    out = b"%PDF-1.7\n"
    off4 = len(out)
    out += (
        b"4 0 obj\n<< /Type /ObjStm /N 3 /First %d /Filter /FlateDecode /Length %d >>\nstream\n"
        % (len(header), len(stream))
        + stream
        + b"\nendstream\nendobj\n"
    )
    off5 = len(out)
    rows = [(0, 0, 0xFF), (2, 4, 0), (2, 4, 1), (2, 4, 2), (1, off4, 0), (1, off5, 0)]
    xz = zlib.compress(b"".join(struct.pack(">BIH", t, a, b) for t, a, b in rows))
    out += (
        b"5 0 obj\n<< /Type /XRef /Size 6 /W [1 4 2] /Root 1 0 R /Filter /FlateDecode /Length %d >>\nstream\n" % len(xz)
        + xz
        + b"\nendstream\nendobj\n"
    )
    return out + b"startxref\n%d\n%%%%EOF\n" % off5


def _pdf_with(kind: str) -> bytes:
    w = PdfWriter()
    w.add_blank_page(595, 842)
    if kind == "javascript":
        with warnings.catch_warnings():  # add_js is deprecated in pypdf 6 but still writes document-level JavaScript
            warnings.simplefilter("ignore", DeprecationWarning)
            w.add_js("app.alert('fixture');")
    elif kind == "attachment":
        w.add_attachment("fixture.txt", b"fixture attachment")
    elif kind == "encrypted":
        w.encrypt(user_password="fixture-user", owner_password="fixture-owner")
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def _jpeg(w: int = 1200, h: int = 1600) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color=(200, 200, 200)).save(buf, format="JPEG", quality=80)
    return buf.getvalue()


# ------------------------------------------------------------------ the worker
@pytest.mark.parametrize(
    ("data", "reason"),
    [
        (b"", "empty"),
        (b"GIF89a....", "Only JPEG, PNG or PDF"),
        (_png_header_only(), "damaged or incomplete"),  # R01: a header alone is not an image
        (b"%PDF-1.7\n/Type /Page\n", "isn't a real PDF"),  # R01: a page token alone is not a PDF
        (_jpeg()[:600], "damaged or incomplete"),  # truncated JPEG
        (_pdf(11), "at most 10 pages"),
        (_pdf_with("javascript"), "scripts or attached files"),
        (_pdf_with("attachment"), "scripts or attached files"),
        (_pdf_with("encrypted"), "password-protected"),
        (_png(20_000, 100), "dimensions"),
    ],
    ids=[
        "empty",
        "gif",
        "png-header-only",
        "fake-pdf",
        "truncated-jpeg",
        "pdf-11-pages",
        "pdf-javascript",
        "pdf-attachment",
        "pdf-encrypted",
        "png-too-wide",
    ],
)
def test_invalid_or_unsafe_files_are_rejected_with_a_reason(data: bytes, reason: str) -> None:
    with pytest.raises(evidence.Rejected, match=reason):
        evidence.inspect(data)


def test_decompression_bombs_are_refused_before_decoding() -> None:
    buf = io.BytesIO()
    Image.new("1", (9_000, 9_000)).save(buf, format="PNG")  # 81 MP, a few KB on disk
    with pytest.raises(evidence.Rejected, match="too many pixels"):
        evidence.inspect(buf.getvalue())


def test_valid_files_become_logical_pages_with_fresh_previews() -> None:
    plain = evidence.inspect(_pdf(3))
    assert plain.content_type == "application/pdf" and len(plain.pages) == 3
    assert len(evidence.inspect(_pdf_object_streams()).pages) == 1  # R01: compressed object streams are valid
    photo = evidence.inspect(_jpeg(3000, 4000))
    assert len(photo.pages) == 1 and max(photo.pages[0].width, photo.pages[0].height) == evidence.PREVIEW_LONG_EDGE_PX
    assert evidence.inspect(_png(500, 400)).warnings  # small photo: a warning, never a rejection on quality alone

    info = PngImagePlugin.PngInfo()
    info.add_text("Comment", "fixture-private-metadata")
    buf = io.BytesIO()
    Image.new("L", (1200, 1600), 128).save(buf, format="PNG", pnginfo=info)
    preview = evidence.inspect(buf.getvalue()).pages[0].preview_png
    assert preview[:8] == b"\x89PNG\r\n\x1a\n" and b"fixture-private-metadata" not in preview  # re-encoded


def test_a_slow_worker_is_a_recoverable_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(evidence, "WORKER_TIMEOUT_S", 0.001)
    with pytest.raises(evidence.Rejected, match="too long"):
        evidence.inspect(_png(seed=90))


# ------------------------------------------------------------------ admission (API)
def test_the_page_cap_counts_pdf_pages_not_files(client: TestClient, published_written: dict[str, Any]) -> None:
    who = _learner(client)
    a = _start(client, who, published_written["chapter"])
    six = _upload(client, who, a["id"], _pdf(6, seed=1))
    assert six.status_code == 201 and len(six.json()["pages"]) == 6
    five = _upload(client, who, a["id"], _pdf(5, seed=2))
    assert five.status_code == 422 and five.json()["code_reason"] == "PAGE_LIMIT"  # 6 + 5 > 10
    four = _upload(client, who, a["id"], _pdf(4, seed=3))
    assert four.status_code == 201 and [p["page_index"] for p in four.json()["pages"]] == [1, 2, 3, 4]
    assert _upload(client, who, a["id"], _png(seed=4)).json()["code_reason"] == "PAGE_LIMIT"  # exactly 10 used
    dup = _upload(client, who, a["id"], _pdf(4, seed=3)).json()
    assert dup["duplicate"] and [p["id"] for p in dup["pages"]] == [p["id"] for p in four.json()["pages"]]
    attempt = client.get(f"/v1/written-attempts/{a['id']}", headers=who.headers).json()
    assert len(attempt["pages"]) == 10 and {p["file_pages"] for p in attempt["pages"]} == {6, 4}


def test_file_and_byte_limits_are_separate(client: TestClient, published_written: dict[str, Any]) -> None:
    who = _learner(client)
    a = _start(client, who, published_written["chapter"])
    with get_sessionmaker()() as db:
        db.execute(
            text(
                'update written_form set caps = caps || \'{"max_files": 2, "max_total_bytes": 200000}\'::jsonb '
                "where id = (select form_id from written_attempt where id = :a)"
            ),
            {"a": a["id"]},
        )
        db.commit()
    assert _upload(client, who, a["id"], _png(seed=11)).status_code == 201
    noise = Image.frombytes("RGB", (1000, 1000), os.urandom(3 * 1000 * 1000))  # incompressible: about 1 MB as JPEG
    buf = io.BytesIO()
    noise.save(buf, format="JPEG", quality=95)
    big = _upload(client, who, a["id"], buf.getvalue())
    assert big.status_code == 422 and big.json()["code_reason"] == "BYTE_LIMIT"
    assert _upload(client, who, a["id"], _png(seed=12)).status_code == 201
    assert _upload(client, who, a["id"], _png(seed=13)).json()["code_reason"] == "FILE_LIMIT"


def test_a_refused_admission_leaves_no_stored_objects(
    client: TestClient, published_written: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    who = _learner(client)
    a = _start(client, who, published_written["chapter"])
    calls = {"n": 0}
    real = service._check_caps

    def second_check_fails(*args: Any) -> None:
        calls["n"] += 1
        if calls["n"] == 1:  # the authoritative check under the lock, after storing (the early check uses plain values)
            from portal_api.errors import Unprocessable

            raise Unprocessable("Fixture: another upload filled the script.", code_reason="PAGE_LIMIT")
        real(*args)

    monkeypatch.setattr(service, "_check_caps", second_check_fails)
    assert _upload(client, who, a["id"], _pdf(2, seed=21)).status_code == 422
    root = storage.get_store().root / a["id"]
    assert not root.exists() or not any(p.is_file() for p in root.rglob("*"))


def test_orphan_sweep_removes_only_old_unreferenced_objects(client: TestClient) -> None:
    import time

    store = storage.get_store()
    orphan = store.put("orphan-fixture/old.bin", b"fixture")
    fresh = store.put("orphan-fixture/new.bin", b"fixture")
    old = time.time() - 7200
    os.utime(store.root / orphan.key, (old, old))
    with get_sessionmaker()() as db:
        removed = service.sweep_orphans(db, older_than_s=3600)
    assert orphan.key in removed and fresh.key not in removed
    assert not store.exists(orphan.key) and store.exists(fresh.key)
    store.discard_uncommitted(fresh.key)


def test_pdf_pages_map_individually_and_seal_pins_their_previews(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    who = _learner(client)
    a = _start(client, who, published_written["chapter"])
    pages = _upload(client, who, a["id"], _pdf(3, seed=31)).json()["pages"]
    m = _map(client, who, a, {"1:a": {"pages": [pages[1]["id"]]}, "1:b": {"pages": [pages[2]["id"]]}}).json()
    assert m["manifest"]["slots"]["1:a"]["pages"] == [pages[1]["id"]]
    sealed = _seal(client, who, a["id"], m["manifest_revision"])
    assert sealed.status_code == 200, sealed.text
    with get_sessionmaker()() as db:
        row = db.execute(
            text("select page_hashes, preview_hashes from written_receipt where attempt_id = :a"), {"a": a["id"]}
        ).one()
    assert set(row[0]) == set(row[1]) == {pages[1]["id"], pages[2]["id"]}
    got = client.get(f"/v1/written-attempts/{a['id']}/pages/{pages[2]['id']}", headers=who.headers)
    assert got.status_code == 200 and got.headers["content-type"] == "image/png"


def test_seal_detects_a_tampered_preview(client: TestClient, published_written: dict[str, Any]) -> None:
    who = _learner(client)
    a = _start(client, who, published_written["chapter"])
    page = _upload(client, who, a["id"], _png(seed=41)).json()["pages"][0]
    m = _map(client, who, a, {"1:a": {"pages": [page["id"]]}, "1:b": {"unanswered": True}}).json()
    path = storage.get_store().root / a["id"] / page["file_id"] / "page-1.png"
    path.write_bytes(path.read_bytes() + b"tampered")
    r = _seal(client, who, a["id"], m["manifest_revision"])
    assert r.status_code == 409 and "preview is missing or damaged" in r.json()["detail"]
