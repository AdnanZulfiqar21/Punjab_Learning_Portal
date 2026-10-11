"""P11.S2.T2 (STUDY-TOOLS-01): personal study tools. Private lesson notes with revision checks (an edit from a stale
copy, or an edit to a note deleted on another device, is refused with the current state so the learner chooses),
topic favourites and saved formulas pinned to the lesson version they came from. Everything is the learner's own and
private. Fixture accounts and content only."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests import test_content_workflow
from tests.test_attempts import _learner
from tests.test_content_workflow import Staff, _chapter, _confirm_rights, _create, _post, _refs, _save, _submitted

team = test_content_workflow.team

EQUATION = {"type": "equation", "latex": "v = u + at", "text_alt": "v equals u plus a t", "display": True}


def _live_lesson(client: TestClient, db: Session, team: dict[str, Staff]) -> str:
    item, _, doc = _submitted(client, db, team)
    _confirm_rights(client, db, doc)
    approve = {"decision": "approve", "comment": "Fixture check"}
    assert _post(client, team["reviewer"], item["id"], "review", approve).status_code == 200
    assert _post(client, team["publisher"], item["id"], "publish").status_code == 200
    return str(item["id"])


def _note(client: TestClient, who: Any, lesson: str, text: str, base: int) -> Any:
    return client.put(f"/v1/me/lessons/{lesson}/note", headers=who.headers, json={"text": text, "base_revision": base})


def test_notes_are_private_and_refuse_stale_or_deleted_copies(
    client: TestClient, db: Session, team: dict[str, Staff]
) -> None:
    lesson = _live_lesson(client, db, team)
    me, other = _learner(client), _learner(client)
    assert client.get(f"/v1/me/lessons/{lesson}/note", headers=me.headers).json()["revision"] == 0

    first = _note(client, me, lesson, "Remember the units.", 0)
    assert first.status_code == 200, first.text
    assert first.json()["revision"] == 1 and first.json()["text"] == "Remember the units."
    assert client.get(f"/v1/me/lessons/{lesson}/note", headers=other.headers).json()["text"] == ""  # private

    # A second device still holding revision 0 can't overwrite: it gets the current note back to choose from.
    stale = _note(client, me, lesson, "Other device text", 0)
    assert stale.status_code == 409 and stale.json()["code_reason"] == "NOTE_CHANGED"
    assert stale.json()["current"]["text"] == "Remember the units." and stale.json()["current"]["revision"] == 1
    assert _note(client, me, lesson, "Remember the units (SI).", 1).json()["revision"] == 2

    # Deleted on one device, edited on another from the old copy: refused as NOTE_DELETED; keeping it restores it.
    deleted = client.delete(f"/v1/me/lessons/{lesson}/note", headers=me.headers, params={"base_revision": 2})
    assert deleted.status_code == 200 and deleted.json()["deleted"] and deleted.json()["text"] == ""
    edit = _note(client, me, lesson, "Edited offline", 2)
    assert edit.status_code == 409 and edit.json()["code_reason"] == "NOTE_DELETED"
    restored = _note(client, me, lesson, "Edited offline", edit.json()["current"]["revision"])
    assert restored.status_code == 200 and not restored.json()["deleted"]

    notes = client.get("/v1/me/notes", headers=me.headers).json()
    assert [(n["lesson_id"], n["text"]) for n in notes] == [(lesson, "Edited offline")]
    assert client.get("/v1/me/notes", headers=other.headers).json() == []
    assert _note(client, me, lesson, "x" * 5001, 4).status_code == 422


def test_notes_need_a_lesson_the_learner_can_read(client: TestClient, db: Session, team: dict[str, Staff]) -> None:
    draft = _submitted(client, db, team)[0]
    me = _learner(client)
    assert _note(client, me, str(draft["id"]), "x", 0).status_code == 404


def test_topic_favourites(client: TestClient, db: Session) -> None:
    from sqlalchemy import select

    from portal_api.modules.curriculum.models import Topic

    chapter, _ = _chapter(db, 11, "biology")
    topic = db.scalars(select(Topic).where(Topic.chapter_id == chapter.id, Topic.retired_at.is_(None))).first()
    assert topic is not None
    me = _learner(client)
    url = f"/v1/me/favourites/topics/{topic.id}"
    assert client.put(url, headers=me.headers).status_code == 204
    assert client.put(url, headers=me.headers).status_code == 204  # idempotent
    favs = client.get("/v1/me/favourites", headers=me.headers).json()
    assert [f["topic_id"] for f in favs] == [str(topic.id)] and favs[0]["grade"] == 11
    assert client.delete(url, headers=me.headers).status_code == 204
    assert client.get("/v1/me/favourites", headers=me.headers).json() == []
    missing = "/v1/me/favourites/topics/00000000-0000-0000-0000-000000000000"
    assert client.put(missing, headers=me.headers).status_code == 404


def test_saved_formulas_are_pinned_to_the_lesson_version(client: TestClient, db: Session) -> None:
    from tests.test_assets import _asset, _upload
    from tests.test_data_minimisation import _jpeg_with_gps
    from tests.test_lesson_blocks import _publish, _staff

    staff = _staff(client, db)
    chapter, doc = _chapter(db, 11, "biology", 11)
    _confirm_rights(client, db, doc)
    image = _upload(client, staff["author"], _asset(client, staff["author"], "image")["id"], _jpeg_with_gps()).json()
    fallback = {"text": "v = u + at", "image_asset_id": image["id"], "alt": "Fixture formula image", "reviewed": True}
    body = {"blocks": [{"type": "paragraph", "text": "Fixture lesson text."}, {**EQUATION, "fallback": fallback}]}
    item = _create(client, staff["author"], chapter, title="Fixture lesson with a formula")
    assert _save(client, staff["author"], item, body=body, refs=_refs(chapter, doc)).status_code == 200
    published = _publish(client, staff, item)
    assert published.status_code == 200, published.text
    lesson = str(item["id"])
    me = _learner(client)
    bad = client.post("/v1/me/formulas", headers=me.headers, json={"lesson_id": lesson, "block_index": 0})
    assert bad.status_code == 422  # only equation blocks are formulas
    saved = client.post("/v1/me/formulas", headers=me.headers, json={"lesson_id": lesson, "block_index": 1})
    assert saved.status_code == 201, saved.text
    again = client.post("/v1/me/formulas", headers=me.headers, json={"lesson_id": lesson, "block_index": 1})
    assert again.json()["id"] == saved.json()["id"]  # saving twice keeps one copy
    listed = client.get("/v1/me/formulas", headers=me.headers).json()
    assert len(listed) == 1 and listed[0]["latex"] == "v = u + at" and listed[0]["text_alt"]
    assert listed[0]["updated_since"] is False
    # A reviewed revision of the lesson is published: the saved copy says so instead of silently going stale.
    rev = _post(client, staff["author"], lesson, "revise", {"reason": "Correct a fixture typo"})
    assert rev.status_code == 200, rev.text
    assert _save(client, staff["author"], rev.json(), body=body, refs=_refs(chapter, doc)).status_code == 200
    assert _publish(client, staff, rev.json()).status_code == 200
    again_listed = client.get("/v1/me/formulas", headers=me.headers).json()
    assert again_listed[0]["updated_since"] is True and again_listed[0]["latex"] == "v = u + at"
    assert client.delete(f"/v1/me/formulas/{saved.json()['id']}", headers=me.headers).status_code == 204
    assert client.get("/v1/me/formulas", headers=me.headers).json() == []
    other = _learner(client)
    assert client.delete(f"/v1/me/formulas/{saved.json()['id']}", headers=other.headers).status_code == 404


def test_study_tools_are_in_the_data_export(client: TestClient, db: Session, team: dict[str, Staff]) -> None:
    from portal_api.modules.identity import privacy

    assert {"study_note", "topic_favourite", "saved_formula"} <= privacy.EXPORTED_TABLES
