"""P11.S1.T3 (DISCOVERY-01): course discovery. Every active book is listed with what is actually published (live
lessons, free previews, practice question families) and an explicit state when nothing is published yet; drafts never
count. Filters: class, track (from the launch manifest), subject, exam and availability. Fixture content only."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests import test_content_workflow
from tests.test_content_workflow import Staff, _chapter, _confirm_rights, _create, _post, _refs, _save

team = test_content_workflow.team
URL = "/v1/discovery"


def _book(body: dict[str, Any], grade: int, subject: str) -> dict[str, Any]:
    return next(b for b in body["books"] if b["grade"] == grade and b["subject"] == subject)


def _lesson(client: TestClient, db: Session, team: dict[str, Staff], index: int, title: str, publish: bool) -> str:
    chapter, doc = _chapter(db, 11, "biology", index)
    _confirm_rights(client, db, doc)
    item = _create(client, team["author"], chapter, title=title)
    assert _save(client, team["author"], item, refs=_refs(chapter, doc)).status_code == 200
    if publish:
        assert _post(client, team["author"], item["id"], "submit", {"note": "ready"}).status_code == 200
        approve = {"decision": "approve", "comment": "Fixture check"}
        assert _post(client, team["reviewer"], item["id"], "review", approve).status_code == 200
        assert _post(client, team["publisher"], item["id"], "publish").status_code == 200
    return str(item["id"])


def test_every_book_is_listed_with_what_is_published(client: TestClient, db: Session, team: dict[str, Staff]) -> None:
    before = _book(client.get(URL).json(), 11, "biology")
    draft = _lesson(client, db, team, 6, "Fixture draft lesson", publish=False)
    premium = _lesson(client, db, team, 6, "Fixture premium lesson", publish=True)
    preview = _lesson(client, db, team, 6, "Fixture preview lesson", publish=True)
    tier = {"tier": "preview", "reason": "Fixture: free sample lesson"}
    assert _post(client, team["publisher"], preview, "access-tier", tier).status_code == 200
    # An Urdu variant of the premium lesson is the same lesson concept: it never counts twice (LESSON-VARIANTS-01).
    body = {"kind": "lesson", "title": "Fixture premium lesson (Urdu)", "translation_of": premium, "language": "ur"}
    urdu = client.post("/v1/studio/items", headers=team["author"].headers, json={**body, "translation_origin": "human"})
    assert urdu.status_code == 201, urdu.text
    chapter, doc = _chapter(db, 11, "biology", 6)
    assert _save(client, team["author"], urdu.json(), refs=_refs(chapter, doc)).status_code == 200
    assert _post(client, team["author"], urdu.json()["id"], "submit", {"note": "ready"}).status_code == 200
    approve = {"decision": "approve", "comment": "Fixture check"}
    assert _post(client, team["reviewer"], urdu.json()["id"], "review", approve).status_code == 200
    assert _post(client, team["publisher"], urdu.json()["id"], "publish").status_code == 200

    r = client.get(URL)
    assert r.status_code == 200 and r.headers["cache-control"].startswith("public")
    body = r.json()
    assert {t["code"] for t in body["tracks"]} == {"pre_medical", "pre_engineering", "ics"}
    assert {(b["grade"], b["subject"]) for b in body["books"]} >= {(11, "biology"), (12, "physics")}
    bio = _book(body, 11, "biology")
    assert bio["live_lessons"] == before["live_lessons"] + 2  # the draft never counts; variants once
    assert bio["preview_lessons"] == before["preview_lessons"] + 1
    assert bio["state"] == "lessons"
    ids = [p["lesson_id"] for p in body["previews"]]
    assert preview in ids and premium not in ids and draft not in ids
    for b in body["books"]:
        assert b["state"] in ("lessons", "practice_only", "not_yet_published")
        if b["live_lessons"] == 0 and b["practice_questions"] == 0:
            assert b["state"] == "not_yet_published"


def test_filters(client: TestClient) -> None:
    xii = client.get(URL, params={"grade": 12}).json()
    assert xii["books"] and {b["grade"] for b in xii["books"]} == {12}  # Class 11 and 12 never mixed
    eng = client.get(URL, params={"track": "pre_engineering"}).json()
    assert {b["subject"] for b in eng["books"]} == {"mathematics", "chemistry", "physics"}
    bio = client.get(URL, params={"subject": "biology", "grade": 11}).json()
    assert [(b["grade"], b["subject"]) for b in bio["books"]] == [(11, "biology")]
    previews = client.get(URL, params={"availability": "previews"}).json()
    assert all(b["preview_lessons"] > 0 for b in previews["books"])
    assert client.get(URL, params={"track": "astronomy"}).status_code == 422
    assert client.get(URL, params={"exam": "NO-SUCH-EXAM"}).status_code == 404
