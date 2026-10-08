"""Opt-in local benchmark for rubric-correction preview and regrade throughput (PR #36/#38 review: scale evidence).

    PORTAL_BENCH=120 uv run pytest -q -s tests/test_bench_regrade.py

Builds N submitted, teacher-marked scripts on one rubric in the disposable test database, approves a correction and
measures the detail/preview request (latency and SQL statement count) and the worker's regrade throughput. These are
single-machine development numbers, not production capacity evidence (that needs the funded staging environment).
Skipped unless PORTAL_BENCH is set.
"""

from __future__ import annotations

import os
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from portal_api.db import get_sessionmaker
from portal_api.modules.written import regrade_jobs
from tests.test_rubric_adjudication import AW, Team

N = int(os.environ.get("PORTAL_BENCH", "0") or 0)


@pytest.mark.skipif(N <= 0, reason="set PORTAL_BENCH=<scripts> to run the local benchmark")
def test_bench_preview_and_regrade(client: TestClient, published_written: dict[str, Any]) -> None:
    team = Team(client, 7, "physics")
    t0 = time.perf_counter()
    for i in range(N):
        _, a = team.sealed(seed=20_000 + i)
        assert team.decide(a["id"], "initial", awards=AW).status_code == 200
    setup_s = time.perf_counter() - t0
    team.correct_rubric(lambda b: b["expected_concepts"].append("Fixture: bench"))
    adj = team.adjudicate().json()

    engine = get_sessionmaker()().get_bind()
    counted = {"q": 0}

    def count(*_: Any) -> None:
        counted["q"] += 1

    timings = []
    event.listen(engine, "before_cursor_execute", count)
    try:
        for _ in range(5):
            t = time.perf_counter()
            r = client.get(f"/v1/studio/written/adjudications/{adj['id']}", headers=team.adjudicator.headers)
            timings.append(time.perf_counter() - t)
            assert r.status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", count)
    queued = client.post(f"/v1/studio/written/adjudications/{adj['id']}/run", headers=team.adjudicator.headers)
    assert queued.status_code == 202
    t = time.perf_counter()
    with get_sessionmaker()() as db:
        processed = regrade_jobs.work(db, batch=50)
    work_s = time.perf_counter() - t
    timings.sort()
    print(
        f"\nBENCH scripts={N} setup={setup_s:.1f}s preview_p50={timings[2] * 1000:.0f}ms "
        f"preview_max={timings[-1] * 1000:.0f}ms preview_sql={counted['q'] // 5} "
        f"regrade={processed} scripts in {work_s:.1f}s ({processed / work_s:.1f}/s)"
    )
    assert processed == N
