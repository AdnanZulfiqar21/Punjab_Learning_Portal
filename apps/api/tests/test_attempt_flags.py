"""P11.S3.T2 (FLAGS-01): in the exam room a learner can flag questions to come back to. Flags are kept with the attempt
(so they survive a refresh and a move to another device), follow the same one-device rule as answers, stop changing
once the time is up or the test is submitted, and never affect the score. Fixture accounts and questions only."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from tests.test_attempt_handoff import _device, _save
from tests.test_attempts import _form, _learner, _op, _set_times, _start


def _flags(client: TestClient, headers: dict[str, str], attempt_id: str, positions: list[int]) -> Any:
    return client.put(f"/v1/attempts/{attempt_id}/flags", headers=headers, json={"positions": positions})


def test_flags_are_kept_with_the_attempt(client: TestClient, physics: dict[str, Any]) -> None:
    who = _learner(client)
    a = _start(client, who, _form(client, who, physics["chapter"], count=4).json()["id"])
    assert a["flagged"] == []
    r = _flags(client, who.headers, a["id"], [3, 1, 3])
    assert r.status_code == 200, r.text
    assert r.json() == {"flagged": [1, 3]}  # unique and in order
    assert client.get(f"/v1/attempts/{a['id']}", headers=who.headers).json()["flagged"] == [1, 3]
    assert _flags(client, who.headers, a["id"], [9]).status_code == 422  # not a question in this test
    assert _flags(client, who.headers, a["id"], []).json() == {"flagged": []}

    other = _learner(client)
    assert _flags(client, other.headers, a["id"], [1]).status_code == 404  # never someone else's attempt


def test_flags_follow_the_device_and_time_rules_and_never_score(client: TestClient, physics: dict[str, Any]) -> None:
    learner = _learner(client)
    laptop, phone = _device(client, learner, "Laptop"), _device(client, learner, "Phone")
    form = _form(client, learner, physics["chapter"], count=2, timed_minutes=5).json()
    a = client.post(f"/v1/practice/forms/{form['id']}/attempt", headers=laptop).json()
    assert _flags(client, laptop, a["id"], [2]).status_code == 200
    blocked = _flags(client, phone, a["id"], [1])
    assert blocked.status_code == 409 and blocked.json()["code_reason"] == "ATTEMPT_ELSEWHERE"
    assert client.post(f"/v1/attempts/{a['id']}/continue-here", headers=phone).json()["flagged"] == [2]

    opt = a["items"][0]["options"][0]["id"]
    assert _save(client, phone, a["id"], _op(1, 1, opt)).json()["results"][0]["disposition"] == "accepted"
    _set_times(a["id"], deadline_offset_s=-10, cutoff_offset_s=-7)
    late = _flags(client, phone, a["id"], [1, 2])
    assert late.status_code == 409  # time is up: flags no longer change

    submitted = client.post(
        f"/v1/attempts/{a['id']}/submit", headers=phone, json={"idempotency_key": uuid.uuid4().hex, "ops": []}
    )
    assert submitted.status_code == 200, submitted.text
    result = client.get(f"/v1/attempts/{a['id']}/result", headers=phone).json()
    assert "flagged" not in result  # flags are a study aid, not part of the result


def test_untimed_attempts_can_flag_until_submitted(client: TestClient, physics: dict[str, Any]) -> None:
    who = _learner(client)
    a = _start(client, who, _form(client, who, physics["chapter"], count=2).json()["id"])
    assert _flags(client, who.headers, a["id"], [1]).status_code == 200
    client.post(
        f"/v1/attempts/{a['id']}/submit", headers=who.headers, json={"idempotency_key": uuid.uuid4().hex, "ops": []}
    )
    assert _flags(client, who.headers, a["id"], [2]).status_code == 409
