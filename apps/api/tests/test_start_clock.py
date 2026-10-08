"""OCT8-07: the authoritative start time is read after every admission wait (real PostgreSQL; technical fixtures).

Another session holds the scope-capacity lock or the learner's entitlement row; the start request is observed waiting
in pg_stat_activity (synchronisation by observation, not a timed sleep), then the lock is released.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from portal_api.modules.written import review
from tests.test_written_attempts import _form, _learner


def _wait_until_blocked(observer: Session, deadline_s: float = 20) -> None:
    end = time.monotonic() + deadline_s
    while time.monotonic() < end:
        waiting = observer.execute(
            text(
                "select count(*) from pg_stat_activity where datname = current_database() "
                "and wait_event_type = 'Lock' and state = 'active'"
            )
        ).scalar()
        observer.rollback()
        if waiting:
            return
        time.sleep(0.02)
    raise AssertionError("the start request never blocked")


def _start_while_held(
    client: TestClient, who: Any, form_id: str, hold: Callable[[Session], None]
) -> tuple[Any, datetime]:
    holder = get_sessionmaker()()
    observer = get_sessionmaker()()
    hold(holder)
    out: dict[str, Any] = {}
    t = threading.Thread(
        target=lambda: out.setdefault("r", client.post(f"/v1/written/forms/{form_id}/attempt", headers=who.headers))
    )
    t.start()
    _wait_until_blocked(observer)
    released_at = holder.execute(text("select clock_timestamp()")).scalar_one()
    holder.commit()
    holder.close()
    observer.close()
    t.join(60)
    return out["r"], released_at


def test_start_time_is_taken_after_the_capacity_wait(client: TestClient, published_written: dict[str, Any]) -> None:
    who = _learner(client)
    form = _form(client, who, published_written["chapter"]).json()["id"]
    key = review.capacity_lock_key(12, "chemistry")
    r, released_at = _start_while_held(
        client, who, form, lambda s: s.execute(text("select pg_advisory_xact_lock(:k)"), {"k": key})
    )
    assert r.status_code == 200, r.text
    a = r.json()
    assert datetime.fromisoformat(a["started_at"]) >= released_at
    assert datetime.fromisoformat(a["upload_cutoff_at"]) >= released_at  # the window is not shortened by the wait


def test_start_time_and_validity_are_decided_after_the_entitlement_wait(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    who = _learner(client)
    form = _form(client, who, published_written["chapter"]).json()["id"]

    def lock_trial(s: Session) -> None:
        s.execute(
            text("select id from entitlement where user_id = :u and source = 'trial' for update"), {"u": str(who.id)}
        )

    r, released_at = _start_while_held(client, who, form, lock_trial)
    assert r.status_code == 200, r.text
    assert datetime.fromisoformat(r.json()["started_at"]) >= released_at

    # The plan ends while the start is waiting: it must be refused, not admitted on a time read before the wait.
    form2 = _form(client, who, published_written["chapter"]).json()["id"]

    def end_trial_while_holding(s: Session) -> None:
        lock_trial(s)
        s.execute(
            text("update entitlement set ends_at = clock_timestamp() where user_id = :u and source = 'trial'"),
            {"u": str(who.id)},
        )

    late, _ = _start_while_held(client, who, form2, end_trial_while_holding)
    assert late.status_code == 403, late.text
