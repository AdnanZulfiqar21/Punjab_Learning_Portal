"""P04.S1.T3: a session that ends mid-attempt loses nothing that reached the server.

A practice test is started and answered on one signed-in device. That session then ends, by sign-out (revocation) or
by expiry: its next write gets 401 and is not applied. Signing in again on the same or another device shows every
answer the server accepted, and the new session takes the test over without a "continue here" step, because the old
holder is gone (HANDOFF-01). The test is then answered and submitted as usual. Technical fixture questions only.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from portal_api.db import get_sessionmaker
from tests.test_attempts import _form, _learner, _op
from tests.test_mcq_corrections import _keys


def _device(client: TestClient, learner: Any, label: str) -> tuple[dict[str, str], str]:
    r = client.post("/v1/sessions", headers=learner.headers, json={"kind": "web", "device_label": label})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['session_token']}"}, r.json()["session"]["id"]


def _end(client: TestClient, how: str, headers: dict[str, str], session_id: str) -> None:
    if how == "sign_out":
        assert client.delete(f"/v1/me/sessions/{session_id}", headers=headers).status_code == 204
        return
    with get_sessionmaker()() as db:  # the session's lifetime runs out
        db.execute(
            text("update user_session set expires_at = clock_timestamp() - interval '1 minute' where id = :s"),
            {"s": session_id},
        )
        db.commit()


@pytest.mark.parametrize("how", ["sign_out", "expiry"])
def test_answers_survive_the_session_ending_mid_attempt(client: TestClient, physics: dict[str, Any], how: str) -> None:
    learner = _learner(client)
    first, first_id = _device(client, learner, "Fixture laptop")
    form = _form(client, learner, physics["chapter"], count=2).json()
    started = client.post(f"/v1/practice/forms/{form['id']}/attempt", headers=first)
    assert started.status_code == 200, started.text
    attempt = started.json()
    keys = _keys(form["id"])
    saved = client.post(f"/v1/attempts/{attempt['id']}/answers", headers=first, json={"ops": [_op(1, 1, keys[1])]})
    assert saved.json()["results"][0]["disposition"] == "accepted"

    _end(client, how, first, first_id)
    late = client.post(f"/v1/attempts/{attempt['id']}/answers", headers=first, json={"ops": [_op(2, 1, keys[2])]})
    assert late.status_code == 401  # not applied

    again, _ = _device(client, learner, "Fixture laptop, signed in again")
    resumed = client.get(f"/v1/attempts/{attempt['id']}", headers=again).json()
    assert resumed["held_elsewhere"] is False  # the old holder is gone: no "continue here" step
    answers = {a["position"]: a["option_id"] for a in resumed["answers"]}
    assert answers.get(1) == keys[1] and answers.get(2) is None  # the accepted answer, and nothing from the late write
    more = client.post(f"/v1/attempts/{attempt['id']}/answers", headers=again, json={"ops": [_op(2, 1, keys[2])]})
    assert more.json()["results"][0]["disposition"] == "accepted"
    done = client.post(
        f"/v1/attempts/{attempt['id']}/submit", headers=again, json={"idempotency_key": uuid.uuid4().hex, "ops": []}
    )
    assert done.status_code == 200, done.text
    result = client.get(f"/v1/attempts/{attempt['id']}/result", headers=again).json()
    assert (result["raw"], result["maximum"]) == (2, 2)
