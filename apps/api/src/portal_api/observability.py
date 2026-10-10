"""Correlation ID propagation (P03.S4.T2): client → API → logs (→ jobs later via the outbox payload).

Also a rolling five-minute window of this process's requests (P16.S1.T3, SERVICE-OVERVIEW-01): status and latency by
route template, summarised into the operator signals (server-error ratio, p50/p95 latency, submission server errors).
It is per process and in memory: a deployment's monitoring aggregates processes. Paths are recorded as route templates,
never with IDs, so no personal data is kept."""

from __future__ import annotations

import logging
import math
import re
import threading
import time
import uuid
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request, Response

HEADER = "X-Correlation-ID"
_VALID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
log = logging.getLogger("portal_api.request")

WINDOW_S = 300
# Final submissions: a server error here can lose a learner's work, so it has its own signal.
SUBMISSION_ROUTES = frozenset({"/v1/attempts/{attempt_id}/submit", "/v1/written-attempts/{attempt_id}/seal"})
_lock = threading.Lock()
_events: deque[tuple[float, str, int, float]] = deque(maxlen=200_000)


def record_request(route: str, status: int, ms: float) -> None:
    with _lock:
        _events.append((time.monotonic(), route, status, ms))


def reset_window() -> None:
    with _lock:
        _events.clear()


def _rank(sorted_ms: list[float], q: float) -> float:
    return sorted_ms[max(0, math.ceil(q * len(sorted_ms)) - 1)] if sorted_ms else 0.0  # nearest-rank percentile


def window_summary() -> dict[str, Any]:
    cutoff = time.monotonic() - WINDOW_S
    with _lock:
        while _events and _events[0][0] < cutoff:
            _events.popleft()
        events = list(_events)
    ms = sorted(e[3] for e in events)
    errors = sum(1 for e in events if e[2] >= 500)
    subs = [e for e in events if e[1] in SUBMISSION_ROUTES]
    sub_errors = sum(1 for e in subs if e[2] >= 500)
    return {
        "requests": len(events),
        "server_errors": errors,
        "server_error_ratio": errors / len(events) if events else 0.0,
        "latency_p50_ms": _rank(ms, 0.5),
        "latency_p95_ms": _rank(ms, 0.95),
        "submissions": len(subs),
        "submission_server_error_ratio": sub_errors / len(subs) if subs else 0.0,
    }


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def correlation(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        incoming = request.headers.get(HEADER, "")
        cid = incoming if _VALID.match(incoming) else uuid.uuid4().hex  # never trust arbitrary header content
        request.state.correlation_id = cid
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            route = getattr(request.scope.get("route"), "path", "unmatched")
            record_request(route, 500, (time.perf_counter() - started) * 1000)
            raise
        route = getattr(request.scope.get("route"), "path", "unmatched")
        record_request(route, response.status_code, (time.perf_counter() - started) * 1000)
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
