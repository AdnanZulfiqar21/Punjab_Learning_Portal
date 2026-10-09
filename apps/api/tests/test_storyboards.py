"""P07.S4.T1/T2 (STORYBOARD-01): scene-by-scene storyboards with source-cited claims, normal review and publication
gates, never learner-readable, exported as a prompt package. Text here is a technical fixture."""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests import test_content_workflow
from tests.test_content_workflow import Staff, _chapter, _confirm_rights, _post, _refs

team = test_content_workflow.team

CHECKS = {c: True for c in ("accuracy", "sources", "pacing", "accessibility", "rights")}


def _body(claim_ref: int = 0) -> dict[str, Any]:
    return {
        "objective": "Fixture objective",
        "outcome": "Fixture outcome",
        "prerequisites": ["Fixture prerequisite"],
        "duration_s": 40,
        "creative_direction": "Fixture: calm pacing, simple diagrams",
        "scenes": [
            {
                "id": "s1",
                "start_s": 0,
                "end_s": 20,
                "visual": "Fixture diagram",
                "on_screen_text": "Fixture title",
                "narration": "Fixture narration one.",
                "equations": ["E = mc^2"],
                "accessibility": "Fixture description of the diagram and the equation.",
                "claims": [{"text": "Fixture claim", "source_ref": claim_ref}],
            },
            {
                "id": "s2",
                "start_s": 20,
                "end_s": 40,
                "visual": "Fixture summary card",
                "narration": "Fixture narration two.",
                "accessibility": "Fixture description of the summary card.",
            },
        ],
    }


def test_storyboard_lifecycle_and_prompt_package(client: TestClient, db: Session, team: dict[str, Staff]) -> None:
    chapter, doc = _chapter(db, 11, "biology", 1)
    item = client.post(
        "/v1/studio/items",
        headers=team["author"].headers,
        json={"kind": "storyboard", "chapter_id": str(chapter.id), "title": "Fixture storyboard"},
    ).json()
    assert item["kind"] == "storyboard" and item["review_checklist"] == list(CHECKS)

    def save(body: dict[str, Any], refs: list[dict[str, Any]]) -> Any:
        current = client.get(f"/v1/studio/items/{item['id']}", headers=team["author"].headers).json()
        return client.put(
            f"/v1/studio/items/{item['id']}/draft",
            headers=team["author"].headers,
            json={"revision": current["working"]["revision"], "body": body, "source_refs": refs},
        )

    gappy = _body()
    gappy["scenes"][1]["start_s"] = 25
    assert save(gappy, _refs(chapter, doc)).status_code == 200  # drafts may be incomplete
    assert _post(client, team["author"], item["id"], "submit").status_code == 422  # gap between scenes
    assert save(_body(claim_ref=3), _refs(chapter, doc)).status_code == 200
    bad_ref = _post(client, team["author"], item["id"], "submit")
    assert bad_ref.status_code == 422 and "source reference 4" in json.dumps(bad_ref.json())
    assert save(_body(), _refs(chapter, doc)).status_code == 200
    assert _post(client, team["author"], item["id"], "submit").status_code == 200
    review = {"decision": "approve", "comment": "Fixture check", "checklist": CHECKS}
    assert _post(client, team["reviewer"], item["id"], "review", review).status_code == 200
    _confirm_rights(client, db, doc)
    assert _post(client, team["publisher"], item["id"], "publish").status_code == 200
    # Never learner-readable: the reviewed video is what learners get, not the storyboard.
    lessons = client.get(f"/v1/chapters/{chapter.id}/lessons").json()
    assert item["id"] not in [x["id"] for x in lessons]

    r = client.get(f"/v1/studio/items/{item['id']}/prompt-package?version=published", headers=team["reviewer"].headers)
    assert r.status_code == 200 and r.headers["content-disposition"].startswith("attachment;")
    pkg = json.loads(r.content)
    assert pkg["format"] == "portal-storyboard-prompt-package" and pkg["version"]["number"] == 1
    scenes = pkg["teaching_constraints"]["scenes"]
    assert scenes[0]["claims"] == [{"text": "Fixture claim", "source_ref": 1}]
    assert "visual" not in scenes[0] and pkg["creative_direction"]["scenes"][0]["visual"] == "Fixture diagram"
    assert pkg["sources"][0]["source_id"] == doc.source_id
    history = client.get(f"/v1/studio/items/{item['id']}/history", headers=team["publisher"].headers).json()
    assert any(h["action"] == "content.prompt_package_exported" for h in history)
    outsider = test_content_workflow.Staff(client, db, ["content_author"], {"grades": [12], "subjects": ["physics"]})
    assert client.get(f"/v1/studio/items/{item['id']}/prompt-package", headers=outsider.headers).status_code == 403
