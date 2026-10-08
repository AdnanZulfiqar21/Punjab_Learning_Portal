"""OCT8-01: slow evidence work (parsing, storage, integrity hashing) must hold no pooled database connection.

A paused parser or hash read stands in for a slow upload; while it is paused, the request that started it must have no
connection checked out, and an unrelated request must still be served from a one-connection pool. Synchronisation is
by events, not sleeps. Technical fixtures only.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from portal_api import db as dbmod
from portal_api.config import get_settings
from portal_api.modules.written import evidence, storage
from tests.test_written_attempts import _learner, _map, _png, _start


@pytest.fixture
def one_connection_pool(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Rebuild the process engine with a single pooled connection for the duration of the test."""
    monkeypatch.setattr(get_settings(), "db_pool_size", 1)
    dbmod.reset_engine()
    yield
    monkeypatch.undo()
    dbmod.reset_engine()


def _paused(target: Callable[..., Any]) -> tuple[Callable[..., Any], threading.Event, threading.Event]:
    entered, release = threading.Event(), threading.Event()

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        entered.set()
        assert release.wait(30), "test never released the paused step"
        return target(*args, **kwargs)

    return wrapper, entered, release


def _run_paused(
    client: TestClient, call: Callable[[], Any], entered: threading.Event, release: threading.Event
) -> tuple[int, int, Any]:
    """Start `call` in a thread, wait until it is paused, then measure the pool and serve an unrelated request."""
    result: dict[str, Any] = {}
    t = threading.Thread(target=lambda: result.setdefault("r", call()))
    t.start()
    assert entered.wait(30), "the slow step was never reached"
    held = dbmod.get_engine().pool.checkedout()
    unrelated = client.get("/v1/catalogue").status_code  # needs the only pooled connection
    release.set()
    t.join(60)
    return held, unrelated, result.get("r")


def test_parsing_and_storing_an_upload_hold_no_connection(
    client: TestClient, published_written: dict[str, Any], monkeypatch: pytest.MonkeyPatch, one_connection_pool: None
) -> None:
    who = _learner(client)
    a = _start(client, who, published_written["chapter"])
    paused, entered, release = _paused(evidence.inspect)
    monkeypatch.setattr(evidence, "inspect", paused)
    held, unrelated, r = _run_paused(
        client,
        lambda: client.post(
            f"/v1/written-attempts/{a['id']}/pages",
            headers={**who.headers, "Content-Type": "application/octet-stream"},
            content=_png(seed=801),
        ),
        entered,
        release,
    )
    assert held == 0, f"{held} connection(s) held while parsing"
    assert unrelated == 200
    assert r.status_code == 201, r.text


def test_seal_integrity_hashing_holds_no_connection(
    client: TestClient, published_written: dict[str, Any], monkeypatch: pytest.MonkeyPatch, one_connection_pool: None
) -> None:
    who = _learner(client)
    a = _start(client, who, published_written["chapter"])
    page = client.post(
        f"/v1/written-attempts/{a['id']}/pages",
        headers={**who.headers, "Content-Type": "application/octet-stream"},
        content=_png(seed=802),
    ).json()["pages"][0]["id"]
    m = _map(client, who, a, {"1:a": {"pages": [page]}, "1:b": {"unanswered": True}}).json()
    store = storage.get_store()
    paused, entered, release = _paused(store.sha256)
    monkeypatch.setattr(store, "sha256", paused)
    held, unrelated, r = _run_paused(
        client,
        lambda: client.post(
            f"/v1/written-attempts/{a['id']}/seal",
            headers=who.headers,
            json={"idempotency_key": "seal-hold-fixture-1", "expected_revision": m["manifest_revision"]},
        ),
        entered,
        release,
    )
    assert held == 0, f"{held} connection(s) held while hashing evidence"
    assert unrelated == 200
    assert r.status_code == 200, r.text


def test_a_refused_upload_still_cleans_up_without_holding_a_connection(
    client: TestClient, published_written: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The admission re-check refuses after storing (the attempt closed meanwhile): stored objects are removed."""
    who = _learner(client)
    a = _start(client, who, published_written["chapter"])
    real_put = storage.get_store().put
    keys: list[str] = []

    def closing_put(key: str, data: bytes) -> Any:
        out = real_put(key, data)
        keys.append(out.key)
        from tests.test_written_attempts import _shift

        _shift(a["id"], cutoff_offset_s=-1)  # the upload window closes while the file is being stored
        return out

    monkeypatch.setattr(storage.get_store(), "put", closing_put)
    r = client.post(
        f"/v1/written-attempts/{a['id']}/pages",
        headers={**who.headers, "Content-Type": "application/octet-stream"},
        content=_png(seed=803),
    )
    assert r.status_code == 409
    assert keys and not any(storage.get_store().exists(k) for k in keys)


def test_saturated_evidence_workers_answer_a_retryable_503(
    client: TestClient, published_written: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    who = _learner(client)
    a = _start(client, who, published_written["chapter"])
    monkeypatch.setattr(evidence, "_slots", threading.BoundedSemaphore(1))
    monkeypatch.setattr(evidence, "WORKER_QUEUE_WAIT_S", 0.01)
    assert evidence._slots.acquire()  # every worker slot is busy
    try:
        r = client.post(
            f"/v1/written-attempts/{a['id']}/pages",
            headers={**who.headers, "Content-Type": "application/octet-stream"},
            content=_png(seed=804),
        )
    finally:
        evidence._slots.release()
    assert r.status_code == 503 and r.json()["title"] == "SERVICE_BUSY" and r.headers["retry-after"] == "10"
