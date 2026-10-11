"""P06.S3.T1 (SURFACES-01): before publication, staff see how an item reaches every delivery surface: the oldest
supported app's rendering (reviewed fallbacks in place of blocks it can't show), language variants, access tier and
what is still missing (fallbacks, alt text, source mapping). Fixture content only."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.test_content_workflow import (  # noqa: F401 - pytest fixture
    Staff,
    _chapter,
    _create,
    _refs,
    _save,
    team,
)

EQ = {"type": "equation", "latex": "E = mc^2", "text_alt": "E equals m c squared"}


def test_the_surface_report_shows_what_each_client_gets_and_what_is_missing(
    client: TestClient,
    db: Session,
    team: dict[str, Staff],  # noqa: F811
) -> None:
    chapter, doc = _chapter(db, 11, "biology", 7)
    author = team["author"]
    item = _create(client, author, chapter, title="Fixture surfaces lesson")
    body: dict[str, Any] = {"blocks": [{"type": "paragraph", "text": "Fixture text."}, EQ]}
    assert _save(client, author, item, body=body).status_code == 200  # no source pages mapped yet
    url = f"/v1/studio/items/{item['id']}/surfaces"
    r = client.get(url, headers=author.headers)
    assert r.status_code == 200, r.text
    rep = r.json()
    assert rep["fallback_blocks"] == 1
    (lesson,) = rep["oldest_client"]
    assert [b["type"] for b in lesson["blocks"]] == ["paragraph", "fallback"]
    assert any("needs a reviewed fallback" in i for i in rep["issues"])
    assert any("source pages" in i for i in rep["issues"])
    assert rep["access"]["tier"] == "premium"
    assert rep["languages"]["present"] == ["en"] and set(rep["languages"]["missing"]) == {"ur", "roman_ur"}

    fixed = {"blocks": [{"type": "paragraph", "text": "Fixture text."}, {**EQ, "fallback": {
        "text": "E = mc²", "image_asset_id": "fixture-asset", "reviewed": True}}]}  # fmt: skip
    current = client.get(f"/v1/studio/items/{item['id']}", headers=author.headers).json()
    assert _save(client, author, current, body=fixed, refs=_refs(chapter, doc)).status_code == 200
    rep = client.get(url, headers=author.headers).json()
    assert not any("needs a reviewed fallback" in i or "source pages" in i for i in rep["issues"])
    assert any("no alt text" in i for i in rep["issues"])  # an image fallback must describe itself
    assert any("asset archive" in i for i in rep["issues"])  # "fixture-asset" names no archived image (ASSETS-01)
    assert rep["oldest_client"][0]["blocks"][1]["text"] == "E = mc²"

    assert client.get(url, headers=team["student"].headers).status_code == 403
    assert client.get(url, headers=team["outsider"].headers).status_code in (403, 404)
