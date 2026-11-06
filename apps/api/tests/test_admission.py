"""ADMISSION-01: bounded request admission (the REL-02 overload collapse)."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from portal_api import admission


def run(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


def test_reads_leave_room_for_writes() -> None:
    async def scenario() -> tuple[bool, bool, bool]:
        a = admission.Admission(4)  # 3 read slots
        for _ in range(3):
            assert await a.acquire(True, 0.05)
        fourth_read = await a.acquire(True, 0.05)  # reads are capped at three quarters
        write = await a.acquire(False, 0.05)  # a save still gets in
        full = await a.acquire(False, 0.05)  # nothing left
        return fourth_read, write, full

    assert run(scenario()) == (False, True, False)


def test_a_waiting_request_gets_the_released_slot() -> None:
    async def scenario() -> bool:
        a = admission.Admission(2)
        assert await a.acquire(False, 0.05)
        assert await a.acquire(False, 0.05)
        waiter = asyncio.create_task(a.acquire(False, 1.0))
        await asyncio.sleep(0.05)
        assert not waiter.done()
        await a.release(False)
        got = await waiter
        assert (a.busy, a.reading) == (2, 0)
        return got

    assert run(scenario()) is True


def test_slot_count_and_minimum() -> None:
    assert admission.default_slots(10) == 20
    assert admission.default_slots(1) == 4
    with pytest.raises(ValueError):
        admission.Admission(1)


def _app(slots: int, hold: asyncio.Event | None = None) -> FastAPI:
    app = FastAPI()
    gate = admission.Admission(slots)
    app.state.gate = gate

    def busy(request: Request) -> JSONResponse:
        return JSONResponse({"title": "SERVICE_BUSY"}, status_code=503, headers={"Retry-After": "5"})

    app.middleware("http")(admission.middleware(gate, 0.05, busy))

    @app.get("/work")
    async def work() -> dict[str, int]:
        return {"busy": gate.busy}

    @app.get("/healthz")
    async def health() -> dict[str, int]:
        return {"busy": gate.busy}

    return app


def test_requests_are_counted_while_inside_and_released_after() -> None:
    app = _app(4)
    with TestClient(app) as c:
        assert c.get("/work").json() == {"busy": 1}
        assert c.get("/work").json() == {"busy": 1}  # the first one's slot came back
        assert c.get("/healthz").json() == {"busy": 0}  # health checks are not counted
        assert app.state.gate.busy == 0


def test_a_full_process_answers_503_with_retry_after() -> None:
    app = _app(4)
    with TestClient(app) as c:
        gate: admission.Admission = app.state.gate
        assert c.get("/work").status_code == 200  # binds the gate to the client's event loop
        gate.busy = gate.reading = 3  # every read slot taken
        r = c.get("/work")
        assert r.status_code == 503
        assert r.headers["Retry-After"] == "5"
        assert c.post("/work").status_code == 405  # a write is admitted (and reaches routing)
        gate.busy = gate.reading = 0


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ({}, True),
        ({"content-type": "multipart/form-data; boundary=x"}, False),
        ({"content-length": str(2 * 1024 * 1024)}, False),
        ({"content-length": "120"}, True),
    ],
)
def test_large_and_multipart_uploads_are_not_counted(headers: dict[str, str], expected: bool) -> None:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/x",
        "headers": [(k.encode(), v.encode()) for k, v in headers.items()],
        "query_string": b"",
    }
    assert admission.counted(Request(scope)) is expected
