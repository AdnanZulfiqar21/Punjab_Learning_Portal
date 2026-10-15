"""P17.S2.T2 (POOL-CAPS-01): every installed command declares its budget class, a fresh process's database pool is
capped at its class's size, and bulk work waits out a scheduled mock window. Fixture profile and session only."""

from __future__ import annotations

import importlib
import tomllib
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from portal_api import budget, db
from portal_api.config import get_settings
from portal_api.db import get_sessionmaker
from tests.test_content_workflow import Staff
from tests.test_mock_sessions import _schedule, _shift
from tests.test_mocks import _publish_profile

SCRIPTS = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]


@pytest.mark.parametrize("command", sorted(budget.ENTRY_POINTS))
def test_every_command_declares_its_budget_class(command: str) -> None:
    module, name = SCRIPTS[command].split(":")
    fn = getattr(importlib.import_module(module), name)
    assert getattr(fn, "budget_class", None) == budget.ENTRY_POINTS[command]


def test_a_fresh_process_gets_its_class_pool_and_a_running_one_keeps_its_own() -> None:
    with pytest.raises(ValueError):
        budget.process_class("no-such-class")
    saved = (db._engine, db._maker, db._pool_cap)
    try:
        db._engine, db._maker, db._pool_cap = None, None, None  # as in a command's own, new process
        size = budget.process_class("bulk")(lambda: db.get_engine().pool.size())()  # type: ignore[attr-defined]
        assert size == 3 == next(p.connections_each for p in budget.PLAN if p.name == "bulk")
        db.get_engine().dispose()
    finally:
        db._engine, db._maker, db._pool_cap = saved
    before = db.get_engine()
    budget.process_class("written.regrade")(lambda: None)()  # this process already has its pool: left alone
    assert db.get_engine() is before and db._pool_cap == saved[2]


def test_bulk_work_waits_out_a_scheduled_mock_window(
    client: TestClient, db: Session, physics: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    code = _publish_profile(client, db, [{"subject": "physics", "grades": [11], "questions": 1}])
    admin = Staff(client, db, ["academic_adjudicator"], mfa=True)
    session = _schedule(client, admin, code)  # starts in an hour
    try:
        with get_sessionmaker()() as s:
            assert budget.bulk_pause_reason(s) is None  # not yet within the margin
        _shift(session["id"], starts_at=10, entry_closes_at=20, window_closes_at=60, results_at=90)
        with get_sessionmaker()() as s:
            reason = budget.bulk_pause_reason(s)
        assert reason is not None and session["title"] in reason  # 10 minutes before the window: paused
        assert budget.bulk_paused_now() == reason
        monkeypatch.setenv("PORTAL_BULK_PAUSE_IN_MOCK_WINDOWS", "false")
        get_settings.cache_clear()
        with get_sessionmaker()() as s:
            assert budget.bulk_pause_reason(s) is None  # the operator turned pausing off
        monkeypatch.delenv("PORTAL_BULK_PAUSE_IN_MOCK_WINDOWS")
        get_settings.cache_clear()
        _shift(session["id"], starts_at=-120, entry_closes_at=-110, window_closes_at=-20, results_at=-10)
        with get_sessionmaker()() as s:
            assert budget.bulk_pause_reason(s) is None  # ended more than the margin ago
    finally:
        with get_sessionmaker()() as s:  # never leave a live window behind for later tests
            s.execute(text("update mock_session set status = 'cancelled' where id = :i"), {"i": session["id"]})
            s.commit()
        get_settings.cache_clear()
