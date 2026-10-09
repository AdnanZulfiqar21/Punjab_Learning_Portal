"""P07.S1.T2 (LESSON-VARIANTS-01): English, Urdu and Roman Urdu variants of one lesson concept, each reviewed on its
own; a missing translation is explicit and never filled in. Technical fixture lessons only."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests import test_content_workflow
from tests.test_content_workflow import Staff, _chapter, _confirm_rights, _create, _post, _refs, _save

team = test_content_workflow.team


def _publish(client: TestClient, team: dict[str, Staff], item: dict[str, Any], chapter: Any, doc: Any) -> None:
    assert _save(client, team["author"], item, refs=_refs(chapter, doc)).status_code == 200
    assert _post(client, team["author"], item["id"], "submit", {"note": "ready"}).status_code == 200
    review = {"decision": "approve", "comment": "Fixture check"}
    assert _post(client, team["reviewer"], item["id"], "review", review).status_code == 200
    assert _post(client, team["publisher"], item["id"], "publish").status_code == 200


def test_variants_are_reviewed_separately_and_missing_languages_are_explicit(
    client: TestClient, db: Session, team: dict[str, Staff]
) -> None:
    chapter, doc = _chapter(db, 11, "biology", 7)
    _confirm_rights(client, db, doc)
    original = _create(client, team["author"], chapter)
    _publish(client, team, original, chapter, doc)
    url = f"/v1/chapters/{chapter.id}/lessons"
    learner = Staff(client, db, [])

    def mine(language: str | None = None) -> dict[str, Any]:
        params = {"language": language} if language else {}
        rows = client.get(url, headers=learner.headers, params=params).json()
        (row,) = [r for r in rows if r["concept_id"] == original["id"]]
        return dict(row)

    before = mine("ur")
    assert before["id"] == original["id"] and before["requested_language_missing"] is True
    assert before["available_languages"] == ["en"]

    body = {"kind": "lesson", "title": "Fixture lesson (Urdu)", "translation_of": original["id"], "language": "ur"}
    assert client.post("/v1/studio/items", headers=team["author"].headers, json=body).status_code == 422  # origin?
    made = client.post(
        "/v1/studio/items", headers=team["author"].headers, json={**body, "translation_origin": "machine_draft"}
    )
    assert made.status_code == 201, made.text
    urdu = made.json()
    assert urdu["concept_id"] == original["id"] and urdu["language"] == "ur" and urdu["chapter_id"] == str(chapter.id)
    assert urdu["translation_origin"] == "machine_draft" and urdu["state"] == "draft"
    again = client.post(
        "/v1/studio/items", headers=team["author"].headers, json={**body, "translation_origin": "human"}
    )
    assert again.status_code == 409 and again.json()["code_reason"] == "LANGUAGE_TAKEN"

    variants = client.get(f"/v1/studio/items/{original['id']}/variants", headers=team["author"].headers).json()
    status = {v["language"]: (v["state"], v["original"]) for v in variants}
    assert status == {"en": ("published", True), "ur": ("draft", False)}  # each its own review status
    assert mine("ur")["requested_language_missing"] is True  # an unreviewed draft is never shown

    _publish(client, team, urdu, chapter, doc)  # a machine draft still needs the independent review
    shown = mine("ur")
    assert shown["id"] == urdu["id"] and shown["requested_language_missing"] is False
    assert shown["available_languages"] == ["en", "ur"] and shown["translation_origin"] == "machine_draft"
    assert mine()["id"] == original["id"]  # English by default, one row per concept
    roman = mine("roman_ur")
    assert roman["id"] == original["id"] and roman["requested_language_missing"] is True
