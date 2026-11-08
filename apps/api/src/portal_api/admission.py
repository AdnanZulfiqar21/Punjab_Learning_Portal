"""ADMISSION-01: bounded request admission for one API process (closes the REL-02 overload collapse).

Request work runs in a bounded worker-thread pool, and a request keeps its pooled database connection across several
thread hops (dependencies, the endpoint, response validation, closing the session). Under overload every worker
thread ended up waiting for a pooled connection while the requests that held the connections waited for a thread to
finish on, so throughput fell from ~110 to ~4 requests a second until the 5 s pool timeout broke the knot (measured
locally, 100 virtual readers on one process).

Admission keeps the number of requests inside the application below the thread pool, so a thread is always free for a
request that holds a connection. Waiting happens here, in the event loop, which costs no thread or connection; a
request not admitted within `api_admission_wait_s` is answered `503 SERVICE_BUSY` with `Retry-After`, quickly and
honestly. Reads (GET/HEAD) may use at most three quarters of the slots, so answer saves and submissions always find
room while catalogue and lesson traffic is heavy (the §5.8 rule: shed reads first, protect saves).

A slot is released when the response starts. A streamed body (a lecture video) holds no slot while it streams. Health
checks and large or multipart uploads (a slow phone upload would hold a slot for its whole transfer) are not counted.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import Response

log = logging.getLogger("portal_api.admission")

UNCOUNTED_PATHS = ("/healthz", "/readyz")
LARGE_BODY_BYTES = 1024 * 1024
READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def default_slots(pool_size: int) -> int:
    """Twice the per-process connection pool: enough to keep every connection busy while others queue for one."""
    return max(4, 2 * pool_size)


class Admission:
    """Slots for one process. `reads` caps how many of `total` read requests may hold at once."""

    def __init__(self, total: int, reads: int | None = None) -> None:
        if total < 2:
            raise ValueError("admission needs at least 2 slots")
        self.total = total
        self.reads = reads if reads is not None else max(1, (total * 3) // 4)
        self.busy = 0
        self.reading = 0
        self._cond: asyncio.Condition | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def _condition(self) -> asyncio.Condition:
        loop = asyncio.get_running_loop()
        if self._cond is None or self._loop is not loop:  # a new event loop (tests): nothing from the old one is live
            self._cond, self._loop = asyncio.Condition(), loop
            self.busy = self.reading = 0
        return self._cond

    def _fits(self, read: bool) -> bool:
        return self.busy < self.total and (not read or self.reading < self.reads)

    async def acquire(self, read: bool, timeout: float) -> bool:
        cond = self._condition()
        async with cond:
            try:
                await asyncio.wait_for(cond.wait_for(lambda: self._fits(read)), timeout)
            except TimeoutError:
                return False
            self.busy += 1
            if read:
                self.reading += 1
            return True

    async def release(self, read: bool) -> None:
        cond = self._condition()
        async with cond:
            self.busy -= 1
            if read:
                self.reading -= 1
            cond.notify_all()


def counted(request: Request) -> bool:
    if request.url.path.startswith(UNCOUNTED_PATHS):
        return False
    if request.headers.get("content-type", "").startswith("multipart/"):
        return False
    try:
        return int(request.headers.get("content-length") or 0) <= LARGE_BODY_BYTES
    except ValueError:
        return True


def middleware(
    admission: Admission, wait_s: float, busy: Callable[[Request], Response]
) -> Callable[[Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]]:
    async def admit(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if not counted(request):
            return await call_next(request)
        read = request.method in READ_METHODS
        if not await admission.acquire(read, wait_s):
            log.warning(
                "admission refused: method=%s path=%s busy=%d", request.method, request.url.path, admission.busy
            )
            return busy(request)
        try:
            return await call_next(request)  # returns when the response starts; a streamed body holds no slot
        finally:
            await admission.release(read)

    return admit
