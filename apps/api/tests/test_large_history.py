"""Large-history check for the learner reports (review OCT9 follow-up). One real submitted test is cloned set-wise into
HISTORY finalised attempts for the same fixture learner (forms, items, attempts and score versions), then progress and
evidence are timed. This is local engineering evidence on a development machine, not a production or scale claim.
Technical fixture questions only."""

from __future__ import annotations

import time
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from portal_api.db import Base, get_sessionmaker
from tests.test_attempts import POOL, _form, _learner, _start
from tests.test_mistake_notebook import _answer, _submit

HISTORY = 1000
BUDGET_S = 3.0  # generous: catches accidental per-attempt queries or quadratic work, not a latency target


def _clone(table: str, src_where: str, overrides: dict[str, str]) -> str:
    cols = [c.name for c in Base.metadata.tables[table].columns]
    exprs = [overrides.get(c, f"src.{c}") for c in cols]
    return (
        f"insert into {table} ({', '.join(cols)}) select {', '.join(exprs)} "  # noqa: S608 - fixed identifiers
        f"from bench_map m cross join {table} src where {src_where}"
    )


def test_reports_stay_fast_with_a_thousand_attempts(client: TestClient, physics: dict[str, Any]) -> None:
    import portal_api.modules.assessment.models
    import portal_api.modules.assessment.notebook  # noqa: F401 - registers every table used below

    learner = _learner(client)
    form = _form(client, learner, physics["chapter"], count=POOL).json()
    attempt = _start(client, learner, form["id"])
    _answer(client, learner, form["id"], attempt, correct={1, 2})
    _submit(client, learner, attempt["id"])
    with get_sessionmaker()() as db:
        db.execute(
            text(
                "create temp table bench_map as select gen_random_uuid() as form_id, gen_random_uuid() as attempt_id, "
                "g as n from generate_series(1, :n) g"
            ),
            {"n": HISTORY},
        )
        p = {"f": form["id"], "a": attempt["id"]}
        db.execute(
            text(_clone("practice_form", "src.id = :f", {"id": "m.form_id", "idempotency_key": "'bench-' || m.n"})), p
        )
        db.execute(
            text(_clone("form_item", "src.form_id = :f", {"id": "gen_random_uuid()", "form_id": "m.form_id"})), p
        )
        db.execute(
            text(
                _clone(
                    "attempt",
                    "src.id = :a",
                    {
                        "id": "m.attempt_id",
                        "form_id": "m.form_id",
                        "started_at": "src.started_at - m.n * interval '50 minutes'",
                        "finalised_at": "src.finalised_at - m.n * interval '50 minutes'",
                    },
                )
            ),
            p,
        )
        db.execute(
            text(
                _clone(
                    "score_version", "src.attempt_id = :a", {"id": "gen_random_uuid()", "attempt_id": "m.attempt_id"}
                )
            ),
            p,
        )
        db.commit()
    timings = {}
    for name, url, params in (
        ("progress", "/v1/me/progress", {}),
        ("evidence", "/v1/me/evidence", {"grade": 11, "subject": "physics"}),
    ):
        started = time.perf_counter()
        r = client.get(url, headers=learner.headers, params=params)
        timings[name] = time.perf_counter() - started
        assert r.status_code == 200, r.text
    progress = client.get("/v1/me/progress", headers=learner.headers).json()
    physics_row = next(s for s in progress["subjects"] if (s["grade"], s["subject"]) == (11, "physics"))
    assert physics_row["tests"] == HISTORY + 1 and physics_row["questions_answered"] == POOL * (HISTORY + 1)
    print(
        f"\nlarge-history timings ({HISTORY + 1} attempts): " + ", ".join(f"{k} {v:.2f}s" for k, v in timings.items())
    )
    assert all(v < BUDGET_S for v in timings.values()), timings
