"""LECTURE-READ-01: a topic's lecture reaches learners only when it is academically approved and its master can be
served; otherwise the topic says the lecture is coming. Development streaming from a local directory, range requests,
and the premium entitlement. Technical fixtures only."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from portal_api.config import get_settings
from portal_api.modules.curriculum.models import Topic
from tests.test_content_workflow import Staff, _chapter, _confirm_rights, _post, _refs
from tests.test_lectures import REVIEW, STORYBOARD_CHECKS, VTT, _asset, _body, _team, _upload, _voice

MASTER = b"\x00\x00\x00\x18ftypmp42" + b"fixture video bytes " * 40  # not a playable film; a sized fixture


@pytest.fixture
def media_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PORTAL_LECTURE_MEDIA_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    monkeypatch.delenv("PORTAL_LECTURE_MEDIA_DIR")
    get_settings.cache_clear()


def _approved_lecture(client: TestClient, db: Session, team: dict[str, Staff], topic_id: str) -> dict[str, Any]:
    chapter, doc = _chapter(db, 11, "biology", 6)
    _confirm_rights(client, db, doc)
    item = client.post(
        "/v1/studio/items",
        headers=team["author"].headers,
        json={"kind": "storyboard", "chapter_id": str(chapter.id), "topic_id": topic_id, "title": "Fixture storyboard"},
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
    voice = _voice(client, team)
    approved = client.post(
        f"/v1/studio/voices/{voice['id']}/approve",
        headers=team["owner"].headers,
        json={"evidence": "Fixture: owner approved this voice"},
    )
    assert approved.status_code == 200, approved.text
    made = client.post(
        "/v1/studio/lectures",
        headers=team["author"].headers,
        json={"storyboard_item_id": item["id"], "narration_language": "roman_ur", "voice_id": voice["id"]},
    )
    assert made.status_code == 201, made.text
    url = f"/v1/studio/lectures/{made.json()['id']}"
    master = {
        "filename": f"fixture-{uuid.uuid4().hex[:6]}.mp4",
        "sha256": hashlib.sha256(MASTER).hexdigest(),
        "bytes": len(MASTER),
        "duration_s": 40,
        "location": "Owner archive (fixture)",
    }
    assert client.put(f"{url}/master", headers=team["author"].headers, json=master).status_code == 200
    caption = _upload(client, team["author"], _asset(client, team["author"], "caption")["id"], VTT).json()
    ok = client.put(
        f"{url}/captions",
        headers=team["author"].headers,
        json={"language": "roman_ur", "asset_version_id": caption["id"]},
    )
    assert ok.status_code == 200, ok.text
    transcript = [{"scene_id": "s1", "text": "Fixture narration one."}, {"scene_id": "s2", "text": "Fixture two."}]
    assert (
        client.put(f"{url}/transcript", headers=team["author"].headers, json={"scenes": transcript}).status_code == 200
    )
    markers = [
        {"scene_id": "s1", "start_s": 0, "label": "Fixture title"},
        {"scene_id": "s2", "start_s": 20, "label": "Summary"},
    ]
    assert client.put(f"{url}/markers", headers=team["author"].headers, json={"scenes": markers}).status_code == 200
    assert client.post(f"{url}/submit", headers=team["author"].headers).status_code == 200
    done = client.post(
        f"{url}/review",
        headers=team["reviewer"].headers,
        json={"decision": "approve", "checklist": REVIEW, "notes": "Fixture: terms and pronunciation checked."},
    )
    assert done.status_code == 200, done.text
    return {**done.json(), "master": master}


def test_a_topic_offers_only_an_approved_servable_lecture(client: TestClient, db: Session, media_dir: Path) -> None:
    team = _team(client, db)
    chapter, _doc = _chapter(db, 11, "biology", 6)
    topic = db.scalars(
        select(Topic)
        .where(Topic.chapter_id == chapter.id, Topic.parent_id.is_(None), Topic.retired_at.is_(None))
        .order_by(Topic.display_order)
    ).first()
    assert topic is not None
    path = f"/v1/topics/{topic.id}/lecture"
    guest = client.get(path)
    assert guest.status_code == 200 and guest.json() == {
        "topic_id": str(topic.id),
        "availability": "coming",
        "lectures": [],
    }

    lecture = _approved_lecture(client, db, team, str(topic.id))
    # Approved, but the master is not on this machine: still "coming", and the stream is not found.
    assert client.get(path).json()["availability"] == "coming"
    assert client.get(f"/v1/lectures/{lecture['id']}/stream", headers=team["author"].headers).status_code == 404

    # A file under the registered name but of another size is not the registered master.
    (media_dir / lecture["master"]["filename"]).write_bytes(b"not the master")
    assert client.get(path).json()["availability"] == "coming"
    (media_dir / lecture["master"]["filename"]).write_bytes(MASTER)

    # Now it is offered. A guest sees it exists but can't watch; staff in scope and entitled learners get a stream.
    shown = client.get(path).json()
    assert shown["availability"] == "available"
    assert shown["lectures"][0]["locked"] is True and shown["lectures"][0]["stream_path"] is None
    assert shown["lectures"][0]["duration_s"] == 40 and shown["lectures"][0]["language"] == "roman_ur"
    assert [m["label"] for m in shown["lectures"][0]["markers"]] == ["Fixture title", "Summary"]
    assert [t["scene_id"] for t in shown["lectures"][0]["transcript"]] == ["s1", "s2"]
    learner = Staff(client, db, [])
    assert client.get(path, headers=learner.headers).json()["lectures"][0]["locked"] is True  # no plan or trial
    staff = client.get(path, headers=team["author"].headers).json()["lectures"][0]
    assert staff["locked"] is False and staff["stream_path"] == f"/v1/lectures/{lecture['id']}/stream"
    outsider = Staff(client, db, ["content_author"], {"grades": [12], "subjects": ["biology"]})
    assert client.get(path, headers=outsider.headers).json()["lectures"][0]["locked"] is True

    stream = client.get(staff["stream_path"], headers=team["author"].headers)
    assert stream.status_code == 200 and stream.content == MASTER
    assert stream.headers["content-type"].startswith("video/mp4") and stream.headers["accept-ranges"] == "bytes"
    part = client.get(staff["stream_path"], headers={**team["author"].headers, "Range": "bytes=0-9"})
    assert part.status_code == 206 and part.content == MASTER[:10]
    assert client.get(staff["stream_path"]).status_code == 404  # guests never stream
    assert client.get(staff["stream_path"], headers=learner.headers).status_code == 404


def test_deployed_roles_refuse_the_development_media_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    from portal_api.config import Settings

    base = {
        "role": "production",
        "database_url": "postgresql+psycopg://u:p@db.internal/portal",
        "public_api_origin": "https://api.example.pk",
        "build_id": "abc123",
        "dev_auth_enabled": False,
        "oidc_issuer": "https://id.example.pk",
        "oidc_audience": "portal",
        "evidence_store": "s3",
        "cors_origins": ["https://app.example.pk"],
    }
    try:
        Settings(**base, lecture_media_dir="C:/videos")
    except Exception as e:
        assert "lecture_media_dir" in str(e)
    else:
        pytest.fail("a deployed role accepted the development media directory")
