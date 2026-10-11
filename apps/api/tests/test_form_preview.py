"""P09.S4.T1 (FORM-PREVIEW-01): a reviewer previews a sample form for any profile version (draft included) before it
is verified or published: the exact learner view, the oldest supported client's view, a separate answer report and
automatic checks for accidental answer hints. Nothing is stored. Fixture questions and patterns only."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from portal_api.modules.assessment import preview
from tests.test_attempts import POOL
from tests.test_content_workflow import Staff

RULES = {
    "source_url": "https://example.invalid/fixture",
    "source_note": "Fixture: technical pattern for tests.",
    "duration_minutes": 30,
    "question_pool": "any",
}


def _draft(client: TestClient, who: Staff, sections: list[dict[str, Any]]) -> str:
    code = f"PREVIEW-{uuid.uuid4().hex[:6].upper()}"
    made = client.post("/v1/admin/exam-profiles", headers=who.headers, json={"code": code, "name": "Fixture preview"})
    pid = next(p["id"] for p in made.json() if p["code"] == code)
    v = client.post(
        f"/v1/admin/exam-profiles/{pid}/versions",
        headers=who.headers,
        json={"year": 2026, "rules": {**RULES, "sections": sections}},
    )
    assert v.status_code in (200, 201), v.text
    return str(v.json()["id"])


def test_a_reviewer_previews_a_draft_pattern_reproducibly(
    client: TestClient, db: Session, physics: dict[str, Any]
) -> None:
    reviewer = Staff(client, db, ["academic_adjudicator"], mfa=True)
    vid = _draft(client, reviewer, [{"subject": "physics", "grades": [11], "questions": 3}])
    url = f"/v1/admin/exam-profile-versions/{vid}/preview"
    first = client.get(url, params={"seed": 42}, headers=reviewer.headers)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["seed"] == 42 and body["shortages"] == [] and len(body["items"]) == 3
    assert [i["item_id"] for i in body["items"]] == [
        i["item_id"] for i in client.get(url, params={"seed": 42}, headers=reviewer.headers).json()["items"]
    ]  # the same seed shows the same form
    text = json.dumps(body)
    assert "correct_option_id" not in text and "explanation" not in text  # the learner views carry no answers
    item = body["items"][0]
    assert item["learner"]["stem"] and len(item["learner"]["options"]) == 4
    assert item["oldest_client"]["fallback_blocks"] == 0

    answers = client.get(f"{url}/answers", params={"seed": 42}, headers=reviewer.headers)
    assert answers.status_code == 200
    keys = {a["position"]: a for a in answers.json()["answers"]}
    assert set(keys) == {1, 2, 3}
    for i in body["items"]:
        assert keys[i["position"]]["item_id"] == i["item_id"]
        assert physics["keys"][i["item_id"]] == keys[i["position"]]["correct_option_id"]

    learner = Staff(client, db, [])
    assert client.get(url, params={"seed": 42}, headers=learner.headers).status_code == 403
    assert client.get(f"{url}/answers", params={"seed": 42}, headers=learner.headers).status_code == 403


def test_a_short_pattern_previews_its_shortages(client: TestClient, db: Session, physics: dict[str, Any]) -> None:
    reviewer = Staff(client, db, ["academic_adjudicator"], mfa=True)
    vid = _draft(client, reviewer, [{"subject": "physics", "grades": [11], "questions": POOL * 40}])
    body = client.get(f"/v1/admin/exam-profile-versions/{vid}/preview", headers=reviewer.headers).json()
    assert body["items"] == [] and body["shortages"][0]["required"] == POOL * 40


def _p(text: str) -> list[dict[str, Any]]:
    return [{"type": "paragraph", "text": text}]


def _body(stem: str, options: list[str], key: int, shuffle: bool = True) -> dict[str, Any]:
    return {
        "stem": _p(stem),
        "options": [{"id": f"o{n + 1}", "blocks": _p(t)} for n, t in enumerate(options)],
        "correct_option_id": f"o{key}",
        "shuffle_options": shuffle,
    }


def test_answer_hint_checks() -> None:
    clean = _body(
        "Which gas do plants take in for photosynthesis?", ["Oxygen", "Carbon dioxide", "Nitrogen", "Argon"], 2
    )
    assert preview.checks(clean) == []
    echoed = _body(
        "Mitochondria are the powerhouse of the cell. What are mitochondria?",
        ["The powerhouse of the cell", "A wall", "A pigment", "A gene"],
        1,
    )
    assert any("appears in the question" in c for c in preview.checks(echoed))
    longest = _body("Pick one.", ["Short", "Tiny", "A much longer and far more detailed correct answer", "Brief"], 3)
    assert any("much longer" in c for c in preview.checks(longest))
    twins = _body("Pick one.", ["Same", "Same", "Other", "Else"], 3)
    assert any("same text" in c for c in preview.checks(twins))
    shuffled = _body("Pick one.", ["Alpha", "Beta", "Gamma", "All of the above"], 4)
    assert any("above" in c for c in preview.checks(shuffled))
    assert not any("above" in c for c in preview.checks({**shuffled, "shuffle_options": False}))
