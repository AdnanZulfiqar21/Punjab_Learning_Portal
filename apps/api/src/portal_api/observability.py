"""Correlation ID propagation (P03.S4.T2): client → API → logs (→ jobs later via the outbox payload)."""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

HEADER = "X-Correlation-ID"
_VALID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
log = logging.getLogger("portal_api.request")


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def correlation(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        incoming = request.headers.get(HEADER, "")
        cid = incoming if _VALID.match(incoming) else uuid.uuid4().hex  # never trust arbitrary header content
        request.state.correlation_id = cid
        started = time.perf_counter()
        response = await call_next(request)
        response.headers[HEADER] = cid
        log.info(
            "request",
            extra={
                "correlation_id": cid,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )
        return response
