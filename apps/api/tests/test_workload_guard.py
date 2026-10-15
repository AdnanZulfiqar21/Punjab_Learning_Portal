"""W09.S1.T3 (WORKLOAD-GUARD-01, WA-AC68): the written workload guard pauses new expensive written work when MCQ saves
or the database are under strain, recovers only after healthy checks, a cooldown and a ramp, and never touches tests
already admitted. Health samples and the database's connection use are set directly purely as test setup."""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from portal_api import budget, observability
from portal_api.db import get_sessionmaker
from portal_api.modules.audit.models import AuditEvent
from portal_api.modules.system import guard
from portal_api.modules.written import automatic, regrade_jobs
from tests.test_content_workflow import Staff
from tests.test_written_attempts import _form, _learner, _png, _start, _upload


@pytest.fixture
def clean_guard(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, float]]:
    """A healthy guard with no samples; the database's connection use is whatever the test sets."""
    level = {"saturation": 0.1}
    monkeypatch.setattr(guard, "_db_saturation", lambda db: level["saturation"])

    def reset() -> None:
        with get_sessionmaker()() as s:
            s.execute(text("delete from workload_guard"))
            s.execute(text("delete from health_sample"))
            s.commit()

    reset()
    yield level
    reset()


def _sample(db: Session, saves: int, slow: int = 0, errors: int = 0) -> None:
    db.add(
        guard.HealthSample(
            process="fixture",
            window_end=db.execute(select(func.clock_timestamp())).scalar_one(),
            window_s=20,
            saves=saves,
            slow_saves=slow,
            save_errors=errors,
            pool_in_use=1,
            pool_size=10,
        )
    )
    db.commit()


def _state(db: Session) -> tuple[str, int]:
    row = guard.check(db, force=True)
    return row.state, row.ramp


def _audited(db: Session, action: str) -> int:
    return int(db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == action)) or 0)


def test_a_sample_counts_this_process_s_saves(db: Session, clean_guard: dict[str, float]) -> None:
    t0 = time.monotonic()
    observability.record_request("/v1/attempts/{attempt_id}/answers", 200, 40.0)
    observability.record_request("/v1/attempts/{attempt_id}/answers", 200, 1500.0)  # over the 1 s budget
    observability.record_request("/v1/attempts/{attempt_id}/submit", 503, 30.0)
    observability.record_request("/v1/catalogue", 500, 5000.0)  # not a save
    s = guard.publish_sample(db, since=t0)
    assert (s.saves, s.slow_saves, s.save_errors) == (3, 1, 1)
    assert s.pool_size >= 1


def test_slow_saves_pause_after_three_checks_but_sparse_traffic_never_does(
    db: Session, clean_guard: dict[str, float]
) -> None:
    _sample(db, saves=10, slow=10)  # every save slow, but too few saves to judge a p95
    assert [_state(db) for _ in range(3)] == [("healthy", 100)] * 3
    db.execute(text("delete from health_sample"))
    _sample(db, saves=100, slow=20)  # 20% over budget
    assert _state(db) == ("healthy", 100)
    assert _state(db) == ("healthy", 100)
    assert _state(db) == ("paused", 0)
    assert "20 of 100 MCQ saves" in guard.current(db).reason  # type: ignore[union-attr]
    assert _audited(db, "workload_guard.paused") >= 1


def test_database_saturation_pauses_at_once_and_recovery_waits_cools_and_ramps(
    db: Session, clean_guard: dict[str, float]
) -> None:
    assert [_state(db) for _ in range(2)] == [("healthy", 100)] * 2
    clean_guard["saturation"] = 0.95
    assert _state(db) == ("paused", 0)
    assert "database connections 95% in use" in guard.current(db).reason  # type: ignore[union-attr]
    clean_guard["saturation"] = 0.1
    assert [_state(db) for _ in range(3)] == [("paused", 0)] * 3  # healthy, but the cooldown hasn't passed
    db.execute(text("update workload_guard set last_fault_at = last_fault_at - interval '6 minutes'"))
    db.commit()
    assert _state(db) == ("recovering", 25)
    _sample(db, saves=100, slow=20)  # any new fault during recovery, even one that needs three checks, pauses again
    assert _state(db) == ("paused", 0)
    db.execute(text("delete from health_sample"))
    # Cooled down already, but three healthy checks must follow the last fault (earlier healthy checks don't count).
    db.execute(text("update workload_guard set last_fault_at = last_fault_at - interval '6 minutes'"))
    db.commit()
    assert [_state(db) for _ in range(2)] == [("paused", 0)] * 2
    assert [_state(db) for _ in range(3)] == [("recovering", 25), ("recovering", 50), ("healthy", 100)]
    assert _audited(db, "workload_guard.recovering") >= 1 and _audited(db, "workload_guard.healthy") >= 1


def test_checks_are_rate_limited_across_processes(db: Session, clean_guard: dict[str, float]) -> None:
    clean_guard["saturation"] = 0.95
    guard.check(db, force=True)
    clean_guard["saturation"] = 0.1
    row = guard.check(db)  # within CHECK_S of the last check: the decided state stands
    assert row.state == "paused" and row.healthy_checks == 0


def test_workers_take_nothing_while_paused_and_their_ramp_share_while_recovering(
    db: Session, clean_guard: dict[str, float], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[Any] = []
    monkeypatch.setattr(
        regrade_jobs,
        "work",
        lambda db, batch, max_batches=None, owner=None: calls.append(("regrade", batch, max_batches)) or 0,
    )
    monkeypatch.setattr(automatic, "run_once", lambda db, assessor, limit=20: calls.append(("auto", limit)) or {})
    clean_guard["saturation"] = 0.95
    _state(db)
    db.execute(text("update workload_guard set checked_at = clock_timestamp()"))
    db.commit()
    assert regrade_jobs.drain(db, 50, owner="fixture") == 0 and automatic.run_guarded(db, object()) == {}  # type: ignore[arg-type]
    assert calls == []
    clean_guard["saturation"] = 0.1
    db.execute(text("update workload_guard set state = 'recovering', ramp = 25, checked_at = clock_timestamp()"))
    db.commit()
    regrade_jobs.drain(db, 50, owner="fixture")
    automatic.run_guarded(db, object())  # type: ignore[arg-type]
    assert calls == [("regrade", 12, 1), ("auto", 5)]
    db.execute(text("update workload_guard set state = 'healthy', ramp = 100, checked_at = clock_timestamp()"))
    db.commit()
    regrade_jobs.drain(db, 50, owner="fixture")
    assert calls[-1] == ("regrade", 50, None)


def test_a_pause_holds_new_written_tests_and_bulk_work_but_never_admitted_work(
    client: TestClient, db: Session, published_written: dict[str, Any], clean_guard: dict[str, float]
) -> None:
    chapter = published_written["chapter"]
    who = _learner(client)
    admitted = _start(client, who, chapter)  # started before the pause
    unstarted = _form(client, who, chapter)
    assert unstarted.status_code == 201
    clean_guard["saturation"] = 0.95
    _state(db)

    built = _form(client, who, chapter)
    assert built.status_code == 503 and built.json()["title"] == "WRITTEN_PAUSED"
    assert built.headers["Retry-After"] == "120"
    start = client.post(f"/v1/written/forms/{unstarted.json()['id']}/attempt", headers=who.headers)
    assert start.status_code == 503 and start.json()["title"] == "WRITTEN_PAUSED"
    # The admitted test goes on: it reopens, and pages still upload.
    again = client.post(f"/v1/written/forms/{admitted['form_id']}/attempt", headers=who.headers)
    assert again.status_code == 200 and again.json()["id"] == admitted["id"]
    assert _upload(client, who, admitted["id"], _png(seed=771)).status_code == 201
    shown = client.get(
        "/v1/written/availability", headers=who.headers, params={"grade": 12, "subject": "chemistry"}
    ).json()
    assert shown["paused"] is True and "marking may take longer" in shown["guard_notice"]
    assert "workload guard" in (budget.bulk_pause_reason(db) or "")
    op = Staff(client, db, ["platform_operator"], mfa=True)
    signal = next(
        s for s in client.get("/v1/ops/signals", headers=op.headers).json() if s["name"] == "written_guard_state"
    )
    assert signal["value"] == 1 and signal["level"] == "alert"

    clean_guard["saturation"] = 0.1
    db.execute(text("update workload_guard set state = 'recovering', ramp = 25"))
    db.commit()
    assert _form(client, who, chapter).status_code == 201  # recovery lets new tests through
    assert (
        "catching up"
        in client.get(
            "/v1/written/availability", headers=who.headers, params={"grade": 12, "subject": "chemistry"}
        ).json()["guard_notice"]
    )
