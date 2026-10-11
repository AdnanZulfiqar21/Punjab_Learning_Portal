"""P07.S3.T2 (MARKERS-01): chapter markers say where each storyboard scene (concept section) starts in the lecture's
master video. They are keyed by the storyboard's stable scene ids, so references stay meaningful across video versions,
and they are pinned to the master they were timed against: a replaced master needs its markers re-timed before the
lecture can be submitted. Technical fixture lectures only."""

from __future__ import annotations

import hashlib
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.test_media_uploads import _lecture

SHA_A = hashlib.sha256(b"fixture master A").hexdigest()
SHA_B = hashlib.sha256(b"fixture master B").hexdigest()
GOOD = [
    {"scene_id": "s1", "start_s": 0, "label": "Fixture title"},
    {"scene_id": "s2", "start_s": 22, "label": "Summary"},
]


def _master(client: TestClient, who: Any, url: str, sha: str, duration: int = 45) -> None:
    body = {
        "filename": "fixture.mp4",
        "sha256": sha,
        "bytes": 10,
        "duration_s": duration,
        "location": "Fixture archive",
    }
    assert client.put(f"{url}/master", headers=who.headers, json=body).status_code == 200


def test_markers_follow_the_storyboard_and_the_master(client: TestClient, db: Session) -> None:
    team, lecture = _lecture(client, db)
    author, url = team["author"], f"/v1/studio/lectures/{lecture['id']}"
    no_master = client.put(f"{url}/markers", headers=author.headers, json={"scenes": GOOD})
    assert no_master.status_code == 422  # markers are timed against a master
    _master(client, author, url, SHA_A)
    before = client.get(url, headers=author.headers).json()
    assert before["markers"] is None and any("scene starts" in m for m in before["missing"])
    assert [p["scene_id"] for p in before["marker_proposal"]] == ["s1", "s2"]  # from the storyboard's planned times

    for bad in (
        [GOOD[1], GOOD[0]],  # out of storyboard order
        GOOD[:1],  # a scene missing
        [{**GOOD[0], "start_s": 3}, GOOD[1]],  # the first scene starts the video
        [GOOD[0], {**GOOD[1], "start_s": 0}],  # not increasing
        [GOOD[0], {**GOOD[1], "start_s": 45}],  # past the end of the master
    ):
        assert client.put(f"{url}/markers", headers=author.headers, json={"scenes": bad}).status_code == 422, bad
    assert client.put(f"{url}/markers", headers=team["reviewer"].headers, json={"scenes": GOOD}).status_code == 403

    ok = client.put(f"{url}/markers", headers=author.headers, json={"scenes": GOOD})
    assert ok.status_code == 200, ok.text
    assert ok.json()["markers"]["master_sha256"] == SHA_A and ok.json()["markers_current"] is True
    assert not any("scene starts" in m or "re-time" in m for m in ok.json()["missing"])

    _master(client, author, url, SHA_B, duration=50)  # a new master: the old timings may no longer fit
    stale = client.get(url, headers=author.headers).json()
    assert stale["markers_current"] is False and any("re-time" in m for m in stale["missing"])
    assert stale["markers"]["scenes"] == GOOD  # kept for reference, not silently trusted
    retimed = client.put(
        f"{url}/markers", headers=author.headers, json={"scenes": [GOOD[0], {**GOOD[1], "start_s": 24}]}
    )
    assert retimed.json()["markers_current"] is True and retimed.json()["markers"]["master_sha256"] == SHA_B
