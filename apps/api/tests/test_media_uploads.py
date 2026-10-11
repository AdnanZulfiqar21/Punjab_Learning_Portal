"""P07.S2.T1 (MEDIA-UPLOAD-01): resumable uploads of a lecture's master video into the private archive (local storage
until the media provider exists, B05). An upload session names the file, its size and duration; chunks must arrive at
the current offset (a repeated chunk is harmless, a gap is refused); the finished file is checked (video signature,
SHA-256 against the owner's record when given) before it becomes the lecture's master. Stale sessions are reconciled.
Technical fixture bytes only: a minimal MP4 signature with padding, not a real video."""

from __future__ import annotations

import hashlib
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from tests.test_content_workflow import Staff
from tests.test_lectures import _published_storyboard, _team, _voice

MB = 1024 * 1024
FIXTURE = b"\x00\x00\x00\x18ftypmp42" + bytes(range(256)) * (5 * 4096)  # ~5 MB technical fixture, MP4 signature


def _lecture(client: TestClient, db: Session) -> tuple[dict[str, Staff], dict[str, Any]]:
    team = _team(client, db)
    storyboard = _published_storyboard(client, db, team)
    voice = _voice(client, team)
    client.post(
        f"/v1/studio/voices/{voice['id']}/approve", headers=team["owner"].headers, json={"evidence": "Fixture approval"}
    )
    body = {"storyboard_item_id": storyboard["id"], "narration_language": "roman_ur", "voice_id": voice["id"]}
    made = client.post("/v1/studio/lectures", headers=team["author"].headers, json=body)
    assert made.status_code == 201, made.text
    return team, made.json()


def _start(client: TestClient, who: Staff, lecture: dict[str, Any], data: bytes, **extra: Any) -> Any:
    body = {
        "filename": "fixture-master.mp4",
        "bytes": len(data),
        "content_type": "video/mp4",
        "duration_s": 240,
        **extra,
    }
    return client.post(f"/v1/studio/lectures/{lecture['id']}/master-upload", headers=who.headers, json=body)


def _chunk(client: TestClient, who: Staff, upload_id: str, offset: int, data: bytes) -> Any:
    return client.put(
        f"/v1/studio/uploads/{upload_id}",
        params={"offset": offset},
        headers={**who.headers, "Content-Type": "application/octet-stream"},
        content=data,
    )


def test_a_master_uploads_in_resumable_chunks_and_becomes_the_lectures_master(client: TestClient, db: Session) -> None:
    team, lecture = _lecture(client, db)
    author = team["author"]
    sha = hashlib.sha256(FIXTURE).hexdigest()
    r = _start(client, author, lecture, FIXTURE, sha256=sha)
    assert r.status_code == 201, r.text
    up = r.json()
    assert up["state"] == "uploading" and up["received"] == 0 and up["chunk_bytes"] >= MB
    uid = up["id"]

    assert _chunk(client, author, uid, 0, FIXTURE[:MB]).json()["received"] == MB
    again = _chunk(client, author, uid, 0, FIXTURE[:MB])  # a retried chunk after a lost response: harmless
    assert again.status_code == 200 and again.json()["received"] == MB
    gap = _chunk(client, author, uid, 2 * MB, FIXTURE[2 * MB : 3 * MB])
    assert (
        gap.status_code == 409 and gap.json()["code_reason"] == "UPLOAD_OFFSET" and gap.json()["expected_offset"] == MB
    )
    resumed = client.get(f"/v1/studio/uploads/{uid}", headers=author.headers).json()
    assert resumed["received"] == MB and resumed["state"] == "uploading"  # the resume point after a dropped connection

    done = _chunk(client, author, uid, MB, FIXTURE[MB:])
    assert done.status_code == 200, done.text
    assert done.json()["state"] == "ready" and done.json()["sha256"] == sha
    master = client.get(f"/v1/studio/lectures/{lecture['id']}", headers=author.headers).json()["master"]
    assert master["sha256"] == sha and master["bytes"] == len(FIXTURE) and master["duration_s"] == 240
    assert master["upload_id"] == uid and "archive" in master["location"].lower()
    assert _chunk(client, author, uid, len(FIXTURE), b"x").status_code == 409  # finished: no more bytes


def test_the_finished_file_is_checked_before_it_is_used(client: TestClient, db: Session) -> None:
    team, lecture = _lecture(client, db)
    author = team["author"]
    wrong = _start(client, author, lecture, FIXTURE, sha256="0" * 64).json()
    out = _chunk(client, author, wrong["id"], 0, FIXTURE).json()
    assert out["state"] == "failed" and "SHA-256" in out["failure"]
    not_video = b"%PDF-1.7 fixture" + bytes(4096)
    bad = _start(client, author, lecture, not_video).json()
    out = _chunk(client, author, bad["id"], 0, not_video).json()
    assert out["state"] == "failed" and "video" in out["failure"]
    assert client.get(f"/v1/studio/lectures/{lecture['id']}", headers=author.headers).json()["master"] is None


def test_upload_rules(client: TestClient, db: Session) -> None:
    team, lecture = _lecture(client, db)
    assert _start(client, team["reviewer"], lecture, FIXTURE).status_code == 403  # only authors produce lectures
    xii = Staff(client, db, ["content_author"], {"grades": [12], "subjects": ["biology"]})
    assert _start(client, xii, lecture, FIXTURE).status_code == 404  # outside the author's class and subject
    too_big = {"filename": "big.mp4", "bytes": 50 * 1024 * MB, "content_type": "video/mp4", "duration_s": 240}
    url = f"/v1/studio/lectures/{lecture['id']}/master-upload"
    assert client.post(url, headers=team["author"].headers, json=too_big).status_code == 422
    other_type = {**too_big, "bytes": 10, "content_type": "application/pdf"}
    assert client.post(url, headers=team["author"].headers, json=other_type).status_code == 422
    up = _start(client, team["author"], lecture, FIXTURE).json()
    assert _chunk(client, xii, up["id"], 0, FIXTURE[:MB]).status_code == 404  # someone else's upload
    over = _chunk(client, team["author"], up["id"], 0, FIXTURE + b"extra")
    assert over.status_code == 422  # more bytes than declared


def test_stale_uploads_are_reconciled(client: TestClient, db: Session) -> None:
    from portal_api.modules.content import uploads

    team, lecture = _lecture(client, db)
    up = _start(client, team["author"], lecture, FIXTURE).json()
    _chunk(client, team["author"], up["id"], 0, FIXTURE[:MB])
    with get_sessionmaker()() as s:
        s.execute(
            text("update media_upload set expires_at = now() - interval '1 minute' where id = :i"), {"i": up["id"]}
        )
        s.commit()
    with get_sessionmaker()() as s:
        report = uploads.reconcile(s)
    assert report["expired"] >= 1
    state = client.get(f"/v1/studio/uploads/{up['id']}", headers=team["author"].headers).json()
    assert state["state"] == "failed" and "expired" in state["failure"]
    assert _chunk(client, team["author"], up["id"], MB, FIXTURE[MB : 2 * MB]).status_code == 409
