"""P11.S3.T3 (RECEIPT-01): beside the frozen submission receipt, the attempt says which of the learner's last changes
were not counted, and why (arrived after time was up, after the test was submitted, or not a valid option). An older
revision overtaken by a newer saved one is not a loss and is not listed. Fixture accounts and questions only."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from tests.test_attempts import _form, _learner, _op, _save_ops, _set_times, _start


def test_late_changes_are_listed_on_the_receipt(client: TestClient, physics: dict[str, Any]) -> None:
    who = _learner(client)
    a = _start(client, who, _form(client, who, physics["chapter"], timed_minutes=10).json()["id"])
    first, second = a["items"][0]["options"][0]["id"], a["items"][0]["options"][1]["id"]
    assert _save_ops(client, who, a["id"], _op(1, 2, first)).json()["results"][0]["disposition"] == "accepted"
    stale = _save_ops(client, who, a["id"], _op(1, 1, second)).json()  # an older revision arriving late: harmless
    assert stale["results"][0]["disposition"] == "stale"
    _set_times(a["id"], deadline_offset_s=-5, cutoff_offset_s=-0.001)
    late = _save_ops(client, who, a["id"], _op(1, 3, second), _op(2, 1, a["items"][1]["options"][0]["id"])).json()
    assert {r["disposition"] for r in late["results"]} == {"late"}

    view = client.get(f"/v1/attempts/{a['id']}", headers=who.headers).json()
    assert view["receipt"]["answered_count"] == 1  # the frozen receipt is unchanged; the losses are listed beside it
    assert [(n["position"], n["reason"]) for n in view["not_counted"]] == [(1, "late"), (2, "late")]
    result = client.get(f"/v1/attempts/{a['id']}/result", headers=who.headers).json()
    assert [n["position"] for n in result["not_counted"]] == [1, 2]


def test_a_clean_submission_lists_nothing(client: TestClient, physics: dict[str, Any]) -> None:
    who = _learner(client)
    a = _start(client, who, _form(client, who, physics["chapter"]).json()["id"])
    _save_ops(client, who, a["id"], _op(1, 1, a["items"][0]["options"][0]["id"]))
    out = client.post(
        f"/v1/attempts/{a['id']}/submit", headers=who.headers, json={"idempotency_key": uuid.uuid4().hex, "ops": []}
    )
    assert out.status_code == 200
    assert client.get(f"/v1/attempts/{a['id']}", headers=who.headers).json()["not_counted"] == []
