"""P08.S1.T1 (PASSAGES-01): passages shared by a question group. A passage is reviewed and published like other
content but never shown on its own. An MCQ names one passage of the same class and subject; a test pins the passage
version it was built with, keeps a passage's questions next to each other and shows the passage with them. Passage
diagrams come through the learner's own attempt. Technical fixture content only."""

from __future__ import annotations

import copy
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.test_assets import _asset, _upload
from tests.test_attempts import _learner, _start
from tests.test_content_workflow import Staff, _chapter, _confirm_rights, _post, _refs
from tests.test_data_minimisation import _jpeg_with_gps
from tests.test_mcq_items import CHECKS, VALID, _new_mcq, _save

BIO11 = {"grades": [11], "subjects": ["biology"]}
PASSAGE_CHECKS = {c: True for c in ("accuracy", "diagrams", "grammar", "mapping")}


def _team(client: TestClient, db: Session) -> dict[str, Staff]:
    return {
        "author": Staff(client, db, ["content_author"], BIO11),
        "reviewer": Staff(client, db, ["subject_reviewer"], BIO11),
        "publisher": Staff(client, db, ["publisher"], BIO11, mfa=True),
    }


def _publish(client: TestClient, team: dict[str, Staff], item_id: str, checks: dict[str, bool]) -> Any:
    assert _post(client, team["author"], item_id, "submit").status_code == 200
    review = {"decision": "approve", "comment": "Fixture check", "checklist": checks}
    assert _post(client, team["reviewer"], item_id, "review", review).status_code == 200
    return _post(client, team["publisher"], item_id, "publish")


def _passage(client: TestClient, team: dict[str, Staff], chapter: Any, doc: Any, blocks: list[Any]) -> dict[str, Any]:
    item = client.post(
        "/v1/studio/items",
        headers=team["author"].headers,
        json={"kind": "passage", "chapter_id": str(chapter.id), "title": "Fixture passage"},
    )
    assert item.status_code == 201, item.text
    p = item.json()
    assert p["kind"] == "passage" and p["review_checklist"] == list(PASSAGE_CHECKS)
    saved = client.put(
        f"/v1/studio/items/{p['id']}/draft",
        headers=team["author"].headers,
        json={"revision": p["working"]["revision"], "body": {"blocks": blocks}, "source_refs": _refs(chapter, doc)},
    )
    assert saved.status_code == 200, saved.text
    assert _publish(client, team, p["id"], PASSAGE_CHECKS).status_code == 200
    return dict(p)


def _question(
    client: TestClient, team: dict[str, Staff], chapter: Any, doc: Any, stem: str, passage: str | None
) -> Any:
    item = _new_mcq(client, team["author"], str(chapter.id))
    body = copy.deepcopy(VALID)
    body["stem"] = [{"type": "paragraph", "text": stem}]
    if passage:
        body["passage_id"] = passage
    assert _save(client, team["author"], item, body, _refs(chapter, doc)).status_code == 200
    return item, _publish(client, team, item["id"], CHECKS)


def test_a_passage_is_shown_with_its_questions_kept_together_and_pinned(client: TestClient, db: Session) -> None:
    team = _team(client, db)
    chapter, doc = _chapter(db, 11, "biology", 9)
    _confirm_rights(client, db, doc)
    figure = _upload(client, team["author"], _asset(client, team["author"], "image")["id"], _jpeg_with_gps()).json()
    text_v1 = "Fixture passage: an experiment description (not academic content)."
    figure_block = {"type": "diagram", "asset_version_id": figure["id"], "alt": "Fixture apparatus", "caption": "F"}
    passage = _passage(client, team, chapter, doc, [{"type": "paragraph", "text": text_v1}, figure_block])
    grouped = [_question(client, team, chapter, doc, f"Fixture grouped stem {n}", passage["id"]) for n in (1, 2)]
    loose = [_question(client, team, chapter, doc, f"Fixture loose stem {n}", None) for n in (1, 2)]
    for _, published in grouped + loose:
        assert published.status_code == 200, published.text
    grouped_ids = {item["id"] for item, _ in grouped}

    learner = _learner(client)
    for _ in range(5):  # chance alone would leave the pair apart in about half of these
        form = client.post(
            "/v1/practice/forms",
            headers={**learner.headers, "Idempotency-Key": uuid.uuid4().hex},
            json={"grade": 11, "subject": "biology", "chapter_ids": [str(chapter.id)], "question_count": 4},
        )
        assert form.status_code == 201, form.text
        a = _start(client, learner, form.json()["id"])
        with_passage = [i["position"] for i in a["items"] if i.get("passage")]
        assert len(with_passage) == 2 and with_passage[1] - with_passage[0] == 1, with_passage  # kept together
    shown = next(i for i in a["items"] if i.get("passage"))["passage"]
    assert shown["blocks"][0]["text"] == text_v1
    figure_url = f"/v1/attempts/{a['id']}/assets/{figure['id']}"
    assert client.get(figure_url, headers=learner.headers).status_code == 200  # passage figures via the attempt

    # A revised passage never changes a test that was already built.
    assert _post(client, team["author"], passage["id"], "revise", {"reason": "Fixture: wording"}).status_code == 200
    current = client.get(f"/v1/studio/items/{passage['id']}", headers=team["author"].headers).json()
    v2 = {"blocks": [{"type": "paragraph", "text": "Fixture passage, version 2."}]}
    saved = client.put(
        f"/v1/studio/items/{passage['id']}/draft",
        headers=team["author"].headers,
        json={"revision": current["working"]["revision"], "body": v2, "source_refs": _refs(chapter, doc)},
    )
    assert saved.status_code == 200
    assert _publish(client, team, passage["id"], PASSAGE_CHECKS).status_code == 200
    again = client.get(f"/v1/attempts/{a['id']}", headers=learner.headers).json()
    assert next(i for i in again["items"] if i.get("passage"))["passage"]["blocks"][0]["text"] == text_v1
    assert {i for i in grouped_ids}  # the grouped questions exist


def test_a_question_names_a_published_passage_of_its_own_class(client: TestClient, db: Session) -> None:
    team = _team(client, db)
    chapter, doc = _chapter(db, 11, "biology", 9)
    _confirm_rights(client, db, doc)
    xii = {
        "author": Staff(client, db, ["content_author"], {"grades": [12], "subjects": ["biology"]}),
        "reviewer": Staff(client, db, ["subject_reviewer"], {"grades": [12], "subjects": ["biology"]}),
        "publisher": Staff(client, db, ["publisher"], {"grades": [12], "subjects": ["biology"]}, mfa=True),
    }
    chapter12, doc12 = _chapter(db, 12, "biology", 1)
    _confirm_rights(client, db, doc12)
    other = _passage(client, xii, chapter12, doc12, [{"type": "paragraph", "text": "Fixture Class XII passage."}])
    mixed = _new_mcq(client, team["author"], str(chapter.id))
    body = {**copy.deepcopy(VALID), "passage_id": other["id"]}
    assert _save(client, team["author"], mixed, body, _refs(chapter, doc)).status_code == 200
    refused = _post(client, team["author"], mixed["id"], "submit")  # caught at submission already
    assert refused.status_code == 422 and "Class XI and XII" in " ".join(refused.json()["errors"]), refused.text
    missing = str(uuid.uuid4())
    item = _new_mcq(client, team["author"], str(chapter.id))
    body = {**copy.deepcopy(VALID), "passage_id": missing}
    assert _save(client, team["author"], item, body, _refs(chapter, doc)).status_code == 200
    submitted = _post(client, team["author"], item["id"], "submit")
    assert submitted.status_code == 422 and "passage" in " ".join(submitted.json()["errors"]).lower()
