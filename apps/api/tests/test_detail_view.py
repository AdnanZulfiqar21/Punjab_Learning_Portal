"""OCT8-06: a higher-detail rendition for marking, from the retained original (technical fixtures only).

These fixtures show the software recovers detail the 2,000 px preview drops. They are not evidence that marking is
accurate; real readability needs approved student-script samples and reviewers."""

from __future__ import annotations

import hashlib
import io
from typing import Any

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from pypdf import PdfWriter

from portal_api.db import get_sessionmaker
from tests.test_content_workflow import Staff
from tests.test_written_attempts import _learner, _map, _seal, _start, _upload

SCOPE = {"grades": [12], "subjects": ["chemistry"]}


def _tiny_marks_photo() -> tuple[bytes, Image.Image]:
    im = Image.new("L", (4000, 6000), 255)
    d = ImageDraw.Draw(im)
    for i in range(40):  # 2-pixel "subscripts" in the top-left tenth: lost at 1/3 scale
        d.rectangle((40 + i * 9, 60, 41 + i * 9, 61), fill=0)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue(), im


def _sealed_case(
    client: TestClient, chapter: str, data: bytes
) -> tuple[Staff, dict[str, Any], list[dict[str, Any]], Staff]:
    learner = _learner(client)
    a = _start(client, learner, chapter)
    pages = _upload(client, learner, a["id"], data).json()["pages"]
    m = _map(client, learner, a, {"1:a": {"pages": [pages[-1]["id"]]}, "1:b": {"unanswered": True}}).json()
    assert _seal(client, learner, a["id"], m["manifest_revision"]).status_code == 200
    with get_sessionmaker()() as db:
        teacher = Staff(client, db, ["subject_reviewer"], SCOPE)
    case = next(
        c
        for c in client.get("/v1/studio/written/queue", headers=teacher.headers).json()
        if c["reference"] == a["id"][:8]
    )
    return learner, case, pages, teacher


def test_a_region_detail_returns_the_original_pixels_the_preview_lost(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    data, original = _tiny_marks_photo()
    learner, case, pages, teacher = _sealed_case(client, published_written["chapter"], data)
    base = f"/v1/studio/written/cases/{case['id']}/pages/{pages[0]['id']}"
    preview = Image.open(io.BytesIO(client.get(base, headers=teacher.headers).content))
    assert max(preview.size) == 2000

    full = client.get(f"{base}/detail", headers=teacher.headers)
    assert full.status_code == 200 and full.headers["cache-control"] == "private, no-store"
    assert max(Image.open(io.BytesIO(full.content)).size) == 4000
    assert full.headers["x-evidence-sha256"] == hashlib.sha256(data).hexdigest()

    region = client.get(f"{base}/detail", params={"region": "0,0,0.1,0.1"}, headers=teacher.headers)
    assert region.status_code == 200, region.text
    got = Image.open(io.BytesIO(region.content)).convert("L")
    want = original.crop((0, 0, 400, 600))
    assert got.size == want.size and got.tobytes() == want.tobytes()  # every original pixel, unchanged
    assert "region=0.0000,0.0000,0.1000,0.1000" in region.headers["x-derivative"]

    outside = client.get(f"{base}/detail", params={"region": "0.95,0.95,0.2,0.2"}, headers=teacher.headers)
    assert outside.status_code == 422
    assert client.get(f"{base}/detail", headers=learner.headers).status_code == 403  # markers only
    with get_sessionmaker()() as db:
        other = Staff(client, db, ["subject_reviewer"], {"grades": [11], "subjects": ["physics"]})
    assert client.get(f"{base}/detail", headers=other.headers).status_code == 404  # out of scope


def test_pdf_detail_renders_the_mapped_page(client: TestClient, published_written: dict[str, Any]) -> None:
    w = PdfWriter()
    w.add_blank_page(595, 842)
    w.add_blank_page(842, 595)  # page 2 is landscape
    w.add_metadata({"/Title": "detail fixture"})
    buf = io.BytesIO()
    w.write(buf)
    _, case, pages, teacher = _sealed_case(client, published_written["chapter"], buf.getvalue())
    r = client.get(f"/v1/studio/written/cases/{case['id']}/pages/{pages[1]['id']}/detail", headers=teacher.headers)
    assert r.status_code == 200 and r.headers["x-evidence-page"] == "2"
    img = Image.open(io.BytesIO(r.content))
    assert img.width > img.height and max(img.size) == 4000  # the landscape page, not page 1
