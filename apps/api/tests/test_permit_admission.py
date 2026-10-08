"""Written permit admission under real PostgreSQL concurrency (review R03; W08.S1.T2, §20.13.4).

The cap is at most two open (unsealed, unexpired) written permits per account. Starts for different forms used to read
the open count before taking any lock, so simultaneous starts could all pass it. Technical fixtures only.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from portal_api.db import get_sessionmaker
from tests.test_written_attempts import _form, _learner, _shift, _start


def _forms(client: TestClient, who: Any, chapter: str, n: int) -> list[str]:
    out = []
    for _ in range(n):
        f = _form(client, who, chapter)
        assert f.status_code == 201, f.text
        out.append(f.json()["id"])
    return out


def _start_all(client: TestClient, who: Any, form_ids: list[str]) -> list[int]:
    barrier = threading.Barrier(len(form_ids))

    def go(form_id: str) -> int:
        barrier.wait()
        return client.post(f"/v1/written/forms/{form_id}/attempt", headers=who.headers).status_code

    with ThreadPoolExecutor(max_workers=len(form_ids)) as pool:
        return sorted(pool.map(go, form_ids))


def test_simultaneous_starts_for_different_forms_respect_the_two_permit_cap(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    for _ in range(3):  # repeat: a race that passes once by luck must not pass the test
        who = _learner(client)
        forms = _forms(client, who, published_written["chapter"], 5)
        codes = _start_all(client, who, forms)
        assert codes.count(200) == 2, codes
        assert sorted(c for c in codes if c != 200) == [403, 403, 403], codes  # ALLOWANCE_EXHAUSTED: open permits
        with get_sessionmaker()() as db:
            open_n = db.execute(
                text(
                    "select count(*) from written_attempt a join written_form f on f.id = a.form_id "
                    "where a.status = 'active' and f.owner_id = (select owner_id from written_form where id = :f)"
                ),
                {"f": forms[0]},
            ).scalar()
            reserved = db.execute(
                text(
                    "select count(*) from allowance_event e where e.kind = 'RESERVED' and e.attempt_id in "
                    "(select a.id from written_attempt a where a.form_id = any(cast(:fs as uuid[])))"
                ),
                {"fs": forms},
            ).scalar()
        assert open_n == 2 and reserved == 2  # no orphan reservation from a refused start


def test_simultaneous_starts_of_the_same_form_create_one_attempt_and_one_reservation(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    who = _learner(client)
    form = _forms(client, who, published_written["chapter"], 1)[0]
    codes = _start_all(client, who, [form] * 4)
    assert codes == [200, 200, 200, 200]  # an idempotent repeat returns the same attempt
    with get_sessionmaker()() as db:
        attempts = db.execute(text("select id from written_attempt where form_id = :f"), {"f": form}).all()
        reserved = db.execute(
            text("select count(*) from allowance_event where kind = 'RESERVED' and attempt_id = :a"),
            {"a": attempts[0][0]},
        ).scalar()
    assert len(attempts) == 1 and reserved == 1


def test_a_permit_past_its_cutoff_is_expired_before_counting(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    who = _learner(client)
    first = _start(client, who, published_written["chapter"])
    _start(client, who, published_written["chapter"])
    _shift(first["id"], cutoff_offset_s=-1)  # the upload window of the first permit has closed
    third = client.post(
        f"/v1/written/forms/{_forms(client, who, published_written['chapter'], 1)[0]}/attempt", headers=who.headers
    )
    assert third.status_code == 200, third.text  # the closed permit no longer blocks a new start
    with get_sessionmaker()() as db:
        status, released = db.execute(
            text(
                "select a.status, (select count(*) from allowance_event e where e.attempt_id = a.id and "
                "e.kind = 'RELEASED') from written_attempt a where a.id = :a"
            ),
            {"a": first["id"]},
        ).one()
    assert status == "expired" and released == 1  # expired by the same rules, its reservation released


def test_start_time_is_taken_after_waiting_for_admission(client: TestClient, published_written: dict[str, Any]) -> None:
    who = _learner(client)
    form = _forms(client, who, published_written["chapter"], 1)[0]
    with get_sessionmaker()() as db:
        user_id = db.execute(text("select owner_id from written_form where id = :f"), {"f": form}).scalar()
    holder = get_sessionmaker()()
    from portal_api.modules.access import service as access

    holder.execute(text("select pg_advisory_xact_lock(:k)"), {"k": access.permit_lock_key(user_id)})
    released_at: dict[str, datetime] = {}

    def release_later() -> None:
        time.sleep(1.5)
        released_at["t"] = holder.execute(text("select clock_timestamp()")).scalar_one()
        holder.commit()
        holder.close()

    t = threading.Thread(target=release_later)
    t.start()
    attempt = client.post(f"/v1/written/forms/{form}/attempt", headers=who.headers).json()
    t.join()
    started = datetime.fromisoformat(attempt["started_at"])
    assert started >= released_at["t"]  # the clock was read after the admission lock, not before the wait
