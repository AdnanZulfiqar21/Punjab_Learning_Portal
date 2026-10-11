"""P07.S2.T4 (ASSETS-01): the owned master archive. Versions are immutable and checksummed with provenance; delivery
copies are derived safely (re-encoded images, validated PDFs, WebVTT captions; diagram sources never served); access
follows the studio scope; retention purges only unreferenced, superseded delivery copies and keeps every master,
which can re-derive a copy. Synthetic fixture files only."""

from __future__ import annotations

import hashlib
import io
from typing import Any

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import text
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from tests.test_content_workflow import Staff, _chapter, _create, _save
from tests.test_data_minimisation import _jpeg_with_gps
from tests.test_evidence import _pdf

BIO = {"grades": [11], "subjects": ["biology"]}
SRC = {"source": "Fixture: drawn by the test suite"}


def _asset(client: TestClient, who: Staff, kind: str, title: str = "Fixture asset") -> dict[str, Any]:
    body = {"kind": kind, "title": title, "grade": 11, "subject": "biology"}
    r = client.post("/v1/studio/assets", headers=who.headers, json=body)
    assert r.status_code == 201, r.text
    return dict(r.json())


def _upload(client: TestClient, who: Staff, asset_id: str, data: bytes, **params: str) -> Any:
    return client.post(
        f"/v1/studio/assets/{asset_id}/versions",
        params={**SRC, **params},
        headers={**who.headers, "Content-Type": "application/octet-stream"},
        content=data,
    )


def _file(client: TestClient, who: Staff, version_id: str, copy: str = "delivery") -> Any:
    return client.get(f"/v1/studio/asset-versions/{version_id}/file", params={"copy": copy}, headers=who.headers)


def test_images_are_archived_with_provenance_and_served_re_encoded(client: TestClient, db: Session) -> None:
    author = Staff(client, db, ["content_author"], BIO)
    outsider = Staff(client, db, ["content_author"], {"grades": [12], "subjects": ["physics"]})
    learner = Staff(client, db, [])
    a = _asset(client, author, "image", "Fixture cell diagram")
    original = _jpeg_with_gps()
    assert _upload(client, author, a["id"], original, source="").status_code == 422  # provenance is required
    v1 = _upload(client, author, a["id"], original, author="Fixture artist", licence="Owner's own work")
    assert v1.status_code == 201, v1.text
    v = v1.json()
    assert v["number"] == 1 and v["delivery_state"] == "ready" and v["media_type"] == "image/jpeg"
    assert v["master_sha256"] == hashlib.sha256(original).hexdigest()
    assert v["provenance"] == {
        "source": SRC["source"],
        "author": "Fixture artist",
        "licence": "Owner's own work",
        "tool": "",
    }
    served = _file(client, author, v["id"])
    assert served.status_code == 200 and served.headers["content-type"] == "image/png"
    assert served.headers["x-content-type-options"] == "nosniff" and b"FixtureCam" not in served.content
    assert not Image.open(io.BytesIO(served.content)).getexif()  # no camera or location metadata
    master = _file(client, author, v["id"], "master")
    assert master.content == original and master.headers["content-disposition"].startswith("attachment")
    v2 = _upload(client, author, a["id"], _jpeg_with_gps()).json()
    assert v2["number"] == 2  # a new upload is a new version; version 1 is unchanged
    detail = client.get(f"/v1/studio/assets/{a['id']}", headers=author.headers).json()
    assert [x["number"] for x in detail["versions"]] == [1, 2]

    assert client.get(f"/v1/studio/assets/{a['id']}", headers=outsider.headers).status_code == 404
    assert _upload(client, outsider, a["id"], original).status_code == 404
    assert _file(client, learner, v["id"]).status_code == 403
    mine = client.get("/v1/studio/assets", params={"grade": 12, "subject": "physics"}, headers=author.headers)
    assert mine.json() == []  # nothing outside the caller's scope is listed


def test_handouts_captions_and_diagram_sources(client: TestClient, db: Session) -> None:
    author = Staff(client, db, ["content_author"], BIO)
    handout = _asset(client, author, "handout")
    h = _upload(client, author, handout["id"], _pdf(2))
    assert h.status_code == 201 and h.json()["pages"] == 2, h.text
    assert _upload(client, author, handout["id"], _jpeg_with_gps()).json()["code_reason"] == "ASSET_INVALID"

    caption = _asset(client, author, "caption")
    assert _upload(client, author, caption["id"], b"not a caption file").json()["code_reason"] == "ASSET_INVALID"
    c = _upload(client, author, caption["id"], b"WEBVTT\n\n00:00.000 --> 00:02.000\nFixture caption\n").json()
    assert _file(client, author, c["id"]).headers["content-type"].startswith("text/vtt")

    source = _asset(client, author, "diagram_source")
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    s = _upload(client, author, source["id"], svg).json()
    assert s["delivery_state"] == "none" and _file(client, author, s["id"]).status_code == 404  # never served
    m = _file(client, author, s["id"], "master")
    assert m.headers["content-type"] == "application/octet-stream"
    assert m.headers["content-disposition"].startswith("attachment")


def _age(version_id: str, days: int) -> None:
    with get_sessionmaker()() as db:
        db.execute(
            text("update content_asset_version set created_at = now() - make_interval(days => :d) where id = :v"),
            {"d": days, "v": version_id},
        )
        db.commit()


def test_retention_keeps_masters_and_referenced_versions(client: TestClient, db: Session) -> None:
    author = Staff(client, db, ["content_author"], BIO)
    publisher = Staff(client, db, ["publisher"], BIO, mfa=True)
    operator = Staff(client, db, ["platform_operator"], mfa=True)
    loose, kept = _asset(client, author, "image", "Fixture loose"), _asset(client, author, "image", "Fixture kept")
    loose_v1 = _upload(client, author, loose["id"], _jpeg_with_gps()).json()
    _upload(client, author, loose["id"], _jpeg_with_gps())
    kept_v1 = _upload(client, author, kept["id"], _jpeg_with_gps()).json()
    _upload(client, author, kept["id"], _jpeg_with_gps())
    for v in (loose_v1, kept_v1):
        _age(v["id"], 40)
    chapter, _ = _chapter(db, 11, "biology", 2)
    lesson = _create(client, author, chapter, title="Fixture lesson using an asset")
    fallback = {"text": "x", "image_asset_id": kept_v1["id"], "alt": "x"}
    eq = {"type": "equation", "latex": "x", "text_alt": "x", "fallback": fallback}
    assert _save(client, author, lesson, body={"blocks": [eq]}).status_code == 200  # a draft names kept v1
    issues = client.get(f"/v1/studio/items/{lesson['id']}/surfaces", headers=author.headers).json()["issues"]
    assert not any("asset archive" in i for i in issues)  # a ready archived image satisfies the surface check

    assert client.post("/v1/studio/assets/retention", headers=author.headers).status_code == 403
    dry = client.post("/v1/studio/assets/retention", headers=operator.headers).json()
    assert loose_v1["id"] in dry["purged"] and kept_v1["id"] not in dry["purged"] and dry["applied"] is False
    assert _file(client, author, loose_v1["id"]).status_code == 200  # a dry run changes nothing
    done = client.post("/v1/studio/assets/retention", params={"apply": True}, headers=operator.headers).json()
    assert loose_v1["id"] in done["purged"]
    assert _file(client, author, loose_v1["id"]).status_code == 404
    assert _file(client, author, loose_v1["id"], "master").status_code == 200  # the master is never deleted
    assert _file(client, author, kept_v1["id"]).status_code == 200  # referenced: kept

    rederive = f"/v1/studio/asset-versions/{loose_v1['id']}/rederive"
    assert client.post(rederive, headers=author.headers).status_code == 403
    back = client.post(rederive, headers=publisher.headers)
    assert back.status_code == 200 and back.json()["delivery_state"] == "ready", back.text
    assert _file(client, author, loose_v1["id"]).status_code == 200
