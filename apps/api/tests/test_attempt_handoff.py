"""P10.S1.T3 (HANDOFF-01): one signed-in device holds an active attempt. Another device sees that it is open
elsewhere and can't write until it explicitly continues there; duplicate tabs on one device still resolve by
revision, never overwriting newer answers. Fixture accounts and questions only."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from tests.test_attempts import _form, _learner, _op

URL = "/v1/attempts/{}"


SESSIONS: dict[str, str] = {}  # bearer header value -> session id


def _device(client: TestClient, learner: Any, label: str) -> dict[str, str]:
    r = client.post("/v1/sessions", headers=learner.headers, json={"kind": "web", "device_label": label})
    assert r.status_code == 201, r.text
    bearer = f"Bearer {r.json()['session_token']}"
    SESSIONS[bearer] = r.json()["session"]["id"]
    return {"Authorization": bearer}


def _save(client: TestClient, headers: dict[str, str], attempt_id: str, *ops: dict[str, Any]) -> Any:
    return client.post(f"/v1/attempts/{attempt_id}/answers", headers=headers, json={"ops": list(ops)})


def test_a_second_device_must_continue_explicitly(client: TestClient, physics: dict[str, Any]) -> None:
    learner = _learner(client)
    laptop, phone = _device(client, learner, "Laptop"), _device(client, learner, "Phone")
    form = _form(client, learner, physics["chapter"], count=2).json()
    started = client.post(f"/v1/practice/forms/{form['id']}/attempt", headers=laptop)
    assert started.status_code == 200 and started.json()["held_elsewhere"] is False
    a = started.json()
    opt = a["items"][0]["options"][0]["id"]
    assert _save(client, laptop, a["id"], _op(1, 1, opt)).json()["results"][0]["disposition"] == "accepted"

    seen = client.get(URL.format(a["id"]), headers=phone)
    assert seen.status_code == 200 and seen.json()["held_elsewhere"] is True  # the phone can see it, read-only
    blocked = _save(client, phone, a["id"], _op(1, 2, opt))
    assert blocked.status_code == 409 and blocked.json()["code_reason"] == "ATTEMPT_ELSEWHERE"
    refused = client.post(
        f"/v1/attempts/{a['id']}/submit", headers=phone, json={"idempotency_key": uuid.uuid4().hex, "ops": []}
    )
    assert refused.status_code == 409 and refused.json()["code_reason"] == "ATTEMPT_ELSEWHERE"

    moved = client.post(f"/v1/attempts/{a['id']}/continue-here", headers=phone)
    assert moved.status_code == 200 and moved.json()["held_elsewhere"] is False
    assert _save(client, phone, a["id"], _op(1, 2, opt)).json()["results"][0]["disposition"] == "accepted"
    old = _save(client, laptop, a["id"], _op(1, 3, opt))  # the laptop now has to continue explicitly too
    assert old.status_code == 409 and old.json()["code_reason"] == "ATTEMPT_ELSEWHERE"
    assert client.get(URL.format(a["id"]), headers=laptop).json()["held_elsewhere"] is True


def test_duplicate_tabs_on_one_device_resolve_by_revision(client: TestClient, physics: dict[str, Any]) -> None:
    learner = _learner(client)
    laptop = _device(client, learner, "Laptop")
    form = _form(client, learner, physics["chapter"], count=2).json()
    a = client.post(f"/v1/practice/forms/{form['id']}/attempt", headers=laptop).json()
    first, second = (o["id"] for o in a["items"][0]["options"][:2])
    newer = _save(client, laptop, a["id"], _op(1, 2, second)).json()["results"][0]
    older = _save(client, laptop, a["id"], _op(1, 1, first)).json()["results"][0]  # a stale tab
    assert (newer["disposition"], older["disposition"]) == ("accepted", "stale")
    answers = {x["position"]: x for x in client.get(URL.format(a["id"]), headers=laptop).json()["answers"]}
    assert answers[1]["option_id"] == second  # never overwritten by the older tab


def test_a_signed_out_device_releases_the_attempt(client: TestClient, physics: dict[str, Any]) -> None:
    learner = _learner(client)
    laptop, phone = _device(client, learner, "Laptop"), _device(client, learner, "Phone")
    form = _form(client, learner, physics["chapter"], count=2).json()
    a = client.post(f"/v1/practice/forms/{form['id']}/attempt", headers=laptop).json()
    gone = client.delete(f"/v1/me/sessions/{SESSIONS[laptop['Authorization']]}", headers=phone)
    assert gone.status_code == 204, gone.text  # the laptop was signed out
    opt = a["items"][0]["options"][0]["id"]
    assert _save(client, phone, a["id"], _op(1, 1, opt)).json()["results"][0]["disposition"] == "accepted"
