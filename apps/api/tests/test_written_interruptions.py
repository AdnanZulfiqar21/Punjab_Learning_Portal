"""W07.S3.T2: interrupted processing journeys keep one receipt and one status.

* After the app closes before the acknowledgement arrives, after a logout and a new sign-in, and on a second device of
  the same account, the learner gets the same receipt and status; a retry with the same key replays it and never
  makes a second one. Another account gets nothing.
* While a teacher has not released marks, the result says "pending" and nothing more: no guessed completion time, no
  draft marks. Once released, the learner is told once, however often the release is replayed.

Real PostgreSQL; technical fixture questions and labelled fixture accounts only.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from tests.test_content_workflow import Staff
from tests.test_written_attempts import _learner, _map, _png, _seal, _start, _upload
from tests.test_written_marking import GOOD, _case_for, _decide, _reviewer, _sealed_script


def _device(client: TestClient, learner: Staff, label: str) -> tuple[dict[str, str], str]:
    """A revocable application session, as each signed-in browser or app installation holds."""
    r = client.post("/v1/sessions", headers=learner.headers, json={"kind": "web", "device_label": label})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['session_token']}"}, r.json()["session"]["id"]


def _attempt(client: TestClient, headers: dict[str, str], attempt_id: str) -> Any:
    return client.get(f"/v1/written-attempts/{attempt_id}", headers=headers)


def test_the_receipt_survives_closure_logout_and_a_second_device(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner = _learner(client)
    laptop, laptop_session = _device(client, learner, "Fixture laptop")
    phone, _ = _device(client, learner, "Fixture phone")
    a = _start(client, learner, published_written["chapter"])
    page = _upload(client, learner, a["id"], _png(seed=int(uuid.uuid4().int % 250))).json()["pages"][0]["id"]
    m = _map(client, learner, a, {"1:a": {"pages": [page]}, "1:b": {"unanswered": True}}).json()

    # The laptop submits; suppose the app closes before the acknowledgement arrives.
    key = uuid.uuid4().hex
    sealed = client.post(
        f"/v1/written-attempts/{a['id']}/seal",
        headers=laptop,
        json={"idempotency_key": key, "expected_revision": m["manifest_revision"]},
    )
    assert sealed.status_code == 200, sealed.text
    receipt = sealed.json()["receipt"]

    # The phone sees the same receipt and status, and retrying the same submission replays it.
    seen = _attempt(client, phone, a["id"]).json()
    assert seen["status"] == "sealed" and seen["receipt"] == receipt
    replay = _seal(client, learner, a["id"], m["manifest_revision"], key)
    assert replay.status_code == 200 and replay.json()["replay"] and replay.json()["receipt"] == receipt

    # Logging out ends that session; signing in again restores the same receipt.
    assert client.delete(f"/v1/me/sessions/{laptop_session}", headers=laptop).status_code == 204
    assert _attempt(client, laptop, a["id"]).status_code == 401
    again, _ = _device(client, learner, "Fixture laptop, signed in again")
    restored = _attempt(client, again, a["id"]).json()
    assert restored["status"] == "sealed" and restored["receipt"] == receipt
    assert restored["pages"] == seen["pages"]  # the same evidence, not a re-upload

    # Nobody else can see it, from any device.
    stranger, _ = _device(client, _learner(client), "Fixture other learner")
    assert _attempt(client, stranger, a["id"]).status_code == 404


def test_review_delays_say_pending_without_a_guess_and_release_notifies_once(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed_script(client, published_written["chapter"])
    phone, _ = _device(client, learner, "Fixture phone")
    pending = client.get(f"/v1/written-attempts/{a['id']}/result", headers=phone).json()
    assert pending["status"] == "pending" and pending["questions"] == [] and pending["total_units"] is None
    assert not {k for k in pending if any(w in k for w in ("eta", "estimate", "expected", "due"))}  # no guessed time

    reviewer = _reviewer(client)
    case = _case_for(client, reviewer, a["id"])
    client.post(f"/v1/studio/written/cases/{case['id']}/lease", headers=reviewer.headers)
    assert _decide(client, reviewer, case["id"], 0, GOOD, release=True).status_code == 200
    replayed = _decide(client, reviewer, case["id"], 0, GOOD, release=True)  # a stale or repeated release
    assert replayed.status_code in (409, 422), replayed.text

    def released_notices(headers: dict[str, str]) -> list[dict[str, Any]]:
        items = client.get("/v1/me/notifications", headers=headers).json()["items"]
        return [n for n in items if n["event"] == "written.result_released"]

    assert len(released_notices(learner.headers)) == 1
    assert released_notices(phone) == released_notices(learner.headers)  # one notice, the same on every device
    assert client.get(f"/v1/written-attempts/{a['id']}/result", headers=phone).json()["status"] == "released"
