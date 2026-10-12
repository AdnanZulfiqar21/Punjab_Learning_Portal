"""P14.S7.T2 (DEVICE-GATE-01): trial access is enforced the same way for lessons, tests and downloads.

An account on the free trial whose app install couldn't be authorized (a device already used for a trial) gets no
protected trial use on that install: premium lessons stay locked, offline study packs hold previews only, and new
practice tests are refused. The same account on the web, and on an authorized install, keeps full access with the
original trial dates. Device verdicts come from the development fixture adapter, not a real device (B07/B08).
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.test_content_workflow import Staff
from tests.test_lesson_access import _mine, _published, crew  # noqa: F401
from tests.test_trial_claims import _install, _native


def _lesson_ids(pack: dict[str, Any]) -> set[str]:
    return {x["id"] for x in json.loads(pack["content"])["lessons"]}


def _device(client: TestClient, who: Staff, install: str, verdict: str) -> dict[str, Any]:
    r = client.post(
        "/v1/me/trial/devices",
        headers={**who.headers, **_native(install)},
        json={"surface": "android", "proof": {"fixture_verdict": verdict}},
    )
    assert r.status_code == 200, r.text
    return dict(r.json())


def test_lessons_tests_and_downloads_follow_the_device_decision(
    client: TestClient,
    db: Session,
    crew: dict[str, Staff],  # noqa: F811
    physics: dict[str, Any],
) -> None:
    item, chapter = _published(client, db, crew)
    learner = Staff(client, db, [])
    trial = client.post("/v1/me/trial", headers=learner.headers).json()["trial"]
    used, fresh = _install(), _install()
    assert _device(client, learner, used, "consumed")["state"] == "review_required"
    assert _device(client, learner, fresh, "clean")["state"] == "device_authorized"

    def on(install: str | None) -> dict[str, str]:
        return {**learner.headers, **(_native(install) if install else {})}

    def practice(install: str | None) -> Any:
        return client.post(
            "/v1/practice/forms",
            headers={**on(install), "Idempotency-Key": uuid.uuid4().hex},
            json={"grade": 11, "subject": "physics", "chapter_ids": [physics["chapter"]], "question_count": 1},
        )

    # The unauthorized install: locked lesson, preview-only pack, no new test.
    lesson, _ = _mine(client, chapter, item["id"], on(used))
    assert lesson["locked"] and lesson["body"] is None
    pack = client.get(f"/v1/me/study-packs/{chapter}", headers=on(used)).json()
    assert pack["manifest"]["includes_premium"] is False and item["id"] not in _lesson_ids(pack)
    refused = practice(used)
    assert refused.status_code == 403 and refused.json()["title"] == "DEVICE_AUTHORIZATION_REQUIRED"
    access = client.get("/v1/me/access", headers=on(used)).json()
    assert access["device_state"] == "device_authorization_required"

    # The web and the authorized install: full access, the same trial dates.
    for install in (None, fresh):
        lesson, _ = _mine(client, chapter, item["id"], on(install))
        assert not lesson["locked"] and lesson["body"]["blocks"]
        pack = client.get(f"/v1/me/study-packs/{chapter}", headers=on(install)).json()
        assert pack["manifest"]["includes_premium"] is True and item["id"] in _lesson_ids(pack)
        assert practice(install).status_code == 201
        assert client.get("/v1/me/access", headers=on(install)).json()["trial"]["ends_at"] == trial["ends_at"]
