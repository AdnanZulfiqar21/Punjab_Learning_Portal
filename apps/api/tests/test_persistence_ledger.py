"""P10.S4.T1 (LEDGER-01): persistence failure cases reconciled against an independent expected-answer ledger.

Each seeded scenario sends answer operations from several tabs with duplicate retries, reordered batches,
acknowledgements lost on the way back and database commit failures (failover) injected mid-request. A plain model
of the §10.5 rules (exact replays keep their first disposition, a reused op_id with another payload is a conflict,
older or equal revisions are stale) predicts every acknowledged disposition and the final answers. The server must
match it exactly, and a submission must score exactly the model's final answers. Fixture questions only.
"""

# ruff: noqa: S311 - seeded, reproducible test data, never secrets
from __future__ import annotations

import random
import sys
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session as OrmSession

from tests.test_attempts import POOL, _form, _learner, _start

SCENARIOS = 10


class Model:
    """The expected-answer ledger: independent of the server's code, only the documented rules."""

    def __init__(self) -> None:
        self.ops: dict[str, tuple[tuple[int, int, str | None], str]] = {}  # op_id -> (payload, disposition)
        self.committed: dict[int, tuple[int, str | None]] = {}  # position -> (revision, option)

    def apply(self, op: dict[str, Any]) -> str:
        payload = (op["position"], op["revision"], op["option_id"])
        if op["op_id"] in self.ops:
            stored, disposition = self.ops[op["op_id"]]
            return disposition if stored == payload else "conflict"
        current = self.committed.get(op["position"])
        disposition = "stale" if current is not None and op["revision"] <= current[0] else "accepted"
        if disposition == "accepted":
            self.committed[op["position"]] = (op["revision"], op["option_id"])
        self.ops[op["op_id"]] = (payload, disposition)
        return disposition


@pytest.fixture
def failover(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """Make the next N commits fail as a lost database connection would (the request then rolls back)."""
    state = {"fail_next": 0, "injected": 0}
    original = OrmSession.commit

    def inside_save() -> bool:  # fail the answer-save commit itself, not e.g. the sign-in bookkeeping before it
        f = sys._getframe(2)
        while f is not None:
            if f.f_code.co_name == "save" and f.f_globals.get("__name__") == "portal_api.modules.assessment.attempts":
                return True
            f = f.f_back  # type: ignore[assignment]
        return False

    def commit(self: OrmSession) -> None:
        if state["fail_next"] > 0 and inside_save():
            state["fail_next"] -= 1
            state["injected"] += 1
            raise OperationalError("COMMIT", {}, Exception("injected failover"))
        original(self)

    monkeypatch.setattr(OrmSession, "commit", commit)
    return state


def _scenario(client: TestClient, physics: dict[str, Any], failover: dict[str, int], seed: int) -> None:
    rng = random.Random(seed)
    learner = _learner(client)
    form = _form(client, learner, physics["chapter"], count=POOL).json()
    attempt = _start(client, learner, form["id"])
    options = {i["position"]: [o["id"] for o in i["options"]] for i in attempt["items"]}

    ops: list[dict[str, Any]] = []
    for _tab in range(rng.randint(1, 3)):  # each tab keeps its own revision counters (so tabs collide)
        revisions: dict[int, int] = {}
        for _ in range(rng.randint(3, 12)):
            p = rng.randint(1, POOL)
            revisions[p] = revisions.get(p, 0) + rng.randint(1, 2)
            choice = rng.choice([*options[p], None]) if rng.random() < 0.15 else rng.choice(options[p])
            ops.append({"op_id": str(uuid.uuid4()), "position": p, "revision": revisions[p], "option_id": choice})
    if ops and rng.random() < 0.3:  # a client bug: an op_id reused with a different payload
        bad = dict(rng.choice(ops))
        bad["option_id"] = None if bad["option_id"] else options[bad["position"]][0]
        ops.append(bad)

    model = Model()
    queue = [o for o in ops for _ in range(rng.choice([1, 1, 2, 3]))]  # duplicate retries
    rng.shuffle(queue)  # out of order
    while queue:
        size = rng.randint(1, 6)
        batch, queue = queue[:size], queue[size:]
        roll = rng.random()
        if roll < 0.15:  # the database fails over during commit: nothing is admitted, the client retries later
            failover["fail_next"] = 1
            r = client.post(f"/v1/attempts/{attempt['id']}/answers", headers=learner.headers, json={"ops": batch})
            assert r.status_code == 503, r.text
            queue += batch
            continue
        r = client.post(f"/v1/attempts/{attempt['id']}/answers", headers=learner.headers, json={"ops": batch})
        assert r.status_code == 200, (seed, r.text)
        expected = [model.apply(o) for o in batch]
        got = [x["disposition"] for x in r.json()["results"]]
        assert got == expected, (seed, batch, got, expected)
        if roll < 0.3:  # the acknowledgement was lost on the way back: the client re-sends the same operations
            queue += batch

    view = client.get(f"/v1/attempts/{attempt['id']}", headers=learner.headers).json()
    server = {a["position"]: (a["revision"], a["option_id"]) for a in view["answers"] if a["revision"] > 0}
    assert server == model.committed, (seed, server, model.committed)

    done = client.post(
        f"/v1/attempts/{attempt['id']}/submit",
        headers=learner.headers,
        json={"idempotency_key": uuid.uuid4().hex, "ops": []},
    )
    assert done.status_code == 200, done.text
    result = client.get(f"/v1/attempts/{attempt['id']}/result", headers=learner.headers).json()
    chosen = {i["position"]: i["chosen"] for i in result["items"]}
    for p in range(1, POOL + 1):
        assert chosen.get(p) == model.committed.get(p, (0, None))[1], (seed, p)  # scored exactly the final answers


def test_answers_survive_retries_reordering_lost_acks_and_failover(
    client: TestClient, physics: dict[str, Any], failover: dict[str, int]
) -> None:
    for seed in range(SCENARIOS):
        _scenario(client, physics, failover, seed)
    assert failover["injected"] > 0  # the failure path really ran
