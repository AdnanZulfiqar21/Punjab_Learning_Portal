"""P07.S4.T3 + P07.S3.T1 (LECTURE-01): lecture production records. A lecture pins a published storyboard version and
is narrated by an owner-approved voice in its narration language (Roman Urdu, Urdu or English). Its master video is
registered by checksum, its transcript is edited per storyboard scene, and its reviewed captions come from the asset
archive (same class and subject). Only an independent subject reviewer's checklist (accuracy, voice/text alignment,
pacing, spelling, diagrams, captions, rights, textbook sources) makes it academically approved; nothing is approved
automatically. Technical fixtures only."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.test_assets import _asset, _upload
from tests.test_content_workflow import Staff, _chapter, _confirm_rights, _post, _refs
from tests.test_storyboards import CHECKS as STORYBOARD_CHECKS
from tests.test_storyboards import _body

BIO11 = {"grades": [11], "subjects": ["biology"]}
VTT = b"WEBVTT\n\n00:00.000 --> 00:20.000\nFixture caption one\n\n00:20.000 --> 00:40.000\nFixture caption two\n"
REVIEW = {
    "accuracy": True,
    "voice_text_alignment": True,
    "pacing": True,
    "spelling": True,
    "diagrams": True,
    "captions": True,
    "rights": True,
    "source_verification": True,
}


def _team(client: TestClient, db: Session) -> dict[str, Staff]:
    return {
        "author": Staff(client, db, ["content_author"], BIO11),
        "reviewer": Staff(client, db, ["subject_reviewer"], BIO11),
        "publisher": Staff(client, db, ["publisher"], BIO11, mfa=True),
        "owner": Staff(client, db, ["owner_admin"], mfa=True),
        "owner_no_mfa": Staff(client, db, ["owner_admin"]),
    }


def _published_storyboard(client: TestClient, db: Session, team: dict[str, Staff]) -> dict[str, Any]:
    chapter, doc = _chapter(db, 11, "biology", 5)
    _confirm_rights(client, db, doc)
    item = client.post(
        "/v1/studio/items",
        headers=team["author"].headers,
        json={"kind": "storyboard", "chapter_id": str(chapter.id), "title": "Fixture lecture storyboard"},
    ).json()
    current = client.get(f"/v1/studio/items/{item['id']}", headers=team["author"].headers).json()
    saved = client.put(
        f"/v1/studio/items/{item['id']}/draft",
        headers=team["author"].headers,
        json={"revision": current["working"]["revision"], "body": _body(), "source_refs": _refs(chapter, doc)},
    )
    assert saved.status_code == 200, saved.text
    assert _post(client, team["author"], item["id"], "submit").status_code == 200
    review = {"decision": "approve", "comment": "Fixture check", "checklist": STORYBOARD_CHECKS}
    assert _post(client, team["reviewer"], item["id"], "review", review).status_code == 200
    assert _post(client, team["publisher"], item["id"], "publish").status_code == 200
    return dict(item)


def _voice(client: TestClient, team: dict[str, Staff], language: str = "roman_ur") -> dict[str, Any]:
    body = {
        "name": f"Fixture voice {uuid.uuid4().hex[:6]}",
        "language": language,
        "tool": "Fixture TTS",
        "voice_ref": "fx-1",
    }
    r = client.post("/v1/studio/voices", headers=team["author"].headers, json=body)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "proposed"
    return dict(r.json())


def test_only_the_owner_approves_narration_voices(client: TestClient, db: Session) -> None:
    team = _team(client, db)
    voice = _voice(client, team)
    url = f"/v1/studio/voices/{voice['id']}/approve"
    evidence = {"evidence": "Fixture: owner listened to the sample and chose this voice"}
    assert client.post(url, headers=team["author"].headers, json=evidence).status_code == 403
    assert client.post(url, headers=team["owner_no_mfa"].headers, json=evidence).status_code == 403
    approved = client.post(url, headers=team["owner"].headers, json=evidence)
    assert approved.status_code == 200 and approved.json()["status"] == "approved", approved.text
    voices = client.get("/v1/studio/voices", headers=team["author"].headers).json()
    assert any(v["id"] == voice["id"] and v["status"] == "approved" for v in voices)


def test_a_lecture_is_approved_only_by_an_independent_review(client: TestClient, db: Session) -> None:
    team = _team(client, db)
    storyboard = _published_storyboard(client, db, team)
    proposed = _voice(client, team)
    approved = _voice(client, team)
    client.post(
        f"/v1/studio/voices/{approved['id']}/approve",
        headers=team["owner"].headers,
        json={"evidence": "Fixture: owner approved this voice"},
    )
    urdu = _voice(client, team, language="ur")
    client.post(
        f"/v1/studio/voices/{urdu['id']}/approve", headers=team["owner"].headers, json={"evidence": "Fixture approval"}
    )

    body = {"storyboard_item_id": storyboard["id"], "narration_language": "roman_ur", "voice_id": proposed["id"]}
    assert (
        client.post("/v1/studio/lectures", headers=team["author"].headers, json=body).status_code == 422
    )  # unapproved
    wrong_language = {**body, "voice_id": urdu["id"]}
    assert client.post("/v1/studio/lectures", headers=team["author"].headers, json=wrong_language).status_code == 422
    made = client.post("/v1/studio/lectures", headers=team["author"].headers, json={**body, "voice_id": approved["id"]})
    assert made.status_code == 201, made.text
    lecture = made.json()
    assert lecture["status"] == "in_production" and lecture["academically_approved"] is False
    assert lecture["grade"] == 11 and lecture["storyboard_version"] == 1
    assert [t["scene_id"] for t in lecture["transcript"]] == ["s1", "s2"]  # starts from the storyboard narration
    url = f"/v1/studio/lectures/{lecture['id']}"

    early = client.post(f"{url}/submit", headers=team["author"].headers)
    assert early.status_code == 422 and len(early.json()["errors"]) >= 2  # no master, no captions yet

    master = {"filename": "fixture-lecture.mp4", "sha256": hashlib.sha256(b"fixture").hexdigest(), "bytes": 7,
              "duration_s": 40, "location": "Owner archive (fixture)"}  # fmt: skip
    assert client.put(f"{url}/master", headers=team["author"].headers, json=master).status_code == 200
    xii = Staff(client, db, ["content_author"], {"grades": [12], "subjects": ["biology"]})
    other = client.post(
        "/v1/studio/assets",
        headers=xii.headers,
        json={"kind": "caption", "title": "Fixture 12", "grade": 12, "subject": "biology"},
    ).json()
    other_v = _upload(client, xii, other["id"], VTT).json()
    caption = _upload(client, team["author"], _asset(client, team["author"], "caption")["id"], VTT).json()
    mixed = client.put(
        f"{url}/captions",
        headers=team["author"].headers,
        json={"language": "roman_ur", "asset_version_id": other_v["id"]},
    )
    assert mixed.status_code == 422  # Class 12 captions never attach to a Class 11 lecture
    ok = client.put(
        f"{url}/captions",
        headers=team["author"].headers,
        json={"language": "roman_ur", "asset_version_id": caption["id"]},
    )
    assert ok.status_code == 200, ok.text
    edited = [{"scene_id": "s1", "text": "Fixture narration one, edited."}, {"scene_id": "s2", "text": "Fixture two."}]
    assert client.put(f"{url}/transcript", headers=team["author"].headers, json={"scenes": edited}).status_code == 200
    assert (
        client.put(f"{url}/transcript", headers=team["author"].headers, json={"scenes": edited[:1]}).status_code == 422
    )

    markers = [
        {"scene_id": "s1", "start_s": 0, "label": "Fixture title"},
        {"scene_id": "s2", "start_s": 20, "label": "Summary"},
    ]
    no_markers = client.post(f"{url}/submit", headers=team["author"].headers)
    assert no_markers.status_code == 422  # chapter markers are part of a finished lecture (MARKERS-01)
    assert client.put(f"{url}/markers", headers=team["author"].headers, json={"scenes": markers}).status_code == 200
    assert client.post(f"{url}/submit", headers=team["author"].headers).status_code == 200
    review = {"decision": "approve", "checklist": REVIEW, "notes": "Fixture: terms and pronunciation checked."}
    assert client.post(f"{url}/review", headers=team["author"].headers, json=review).status_code == 403  # producer
    incomplete = {**review, "checklist": {**REVIEW, "source_verification": False}}
    assert client.post(f"{url}/review", headers=team["reviewer"].headers, json=incomplete).status_code == 422
    done = client.post(f"{url}/review", headers=team["reviewer"].headers, json=review)
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "approved" and done.json()["academically_approved"] is True
    assert done.json()["review"]["notes"] == review["notes"]
    assert client.put(f"{url}/master", headers=team["author"].headers, json=master).status_code == 409  # frozen
