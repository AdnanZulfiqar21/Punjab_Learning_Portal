"""P18.S1.T2: systematic authorisation checks over every API route (AUTHZ-01).

1. The set of routes reachable without a principal is pinned. A new unauthenticated route fails this test until it
   is added here deliberately, with a reason.
2. Every other route answers an anonymous request with 401, whatever the method, parameters or body.
3. A signed-in learner with no staff role never gets a success, or a server error, from staff, studio, ops or admin
   routes.
Object-level A/B checks (another learner's attempts, tickets, screenshots, imports and so on) live with each module's
tests; this file guards the whole surface against regressions.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from portal_api.db import get_sessionmaker
from portal_api.main import app
from tests.test_content_workflow import Staff

# method path -> why it is public (or optional-auth)
PUBLIC = {
    "GET /healthz": "liveness probe",
    "GET /readyz": "readiness probe",
    "GET /v1/runtime-config": "public client configuration (no secrets; tested in test_config)",
    "GET /v1/catalogue": "public catalogue structure",
    "GET /v1/grades/{grade}/subjects/{subject}/book": "public catalogue structure",
    "GET /v1/books/{book_id}": "public catalogue structure",
    "GET /v1/chapters/{chapter_id}": "public catalogue structure",
    "GET /v1/search": "public catalogue search (published content only)",
    "GET /v1/chapters/{chapter_id}/lessons": "optional auth: previews public, premium bodies need access (R07)",
    "GET /v1/help/articles": "published help articles",
    "GET /v1/help/articles/{slug}": "published help articles",
    "GET /v1/status": "public incident status",
    "POST /v1/dev-auth/register": "development/test identity adapter only (not mounted in production)",
    "POST /v1/dev-auth/token": "development/test identity adapter only (not mounted in production)",
}
STAFF_PREFIXES = ("/v1/studio", "/v1/staff", "/v1/ops", "/v1/admin")


def _routes() -> Iterator[APIRoute]:
    def walk(routes: list[object]) -> Iterator[APIRoute]:
        for r in routes:
            if isinstance(r, APIRoute):
                yield r
            else:
                inner = getattr(r, "router", None) or getattr(r, "original_router", None)
                if inner is not None:
                    yield from walk(inner.routes)

    yield from walk(list(app.routes))


def _needs_principal(r: APIRoute) -> bool:
    stack, seen = [r.dependant], set()
    while stack:
        d = stack.pop()
        if d.call is not None:
            seen.add(getattr(d.call, "__qualname__", ""))
        stack.extend(d.dependencies)
    return any(q.startswith("current_principal") for q in seen)


def _url(path: str) -> str:
    return re.sub(r"\{[^}]+\}", lambda _: str(uuid.uuid4()), path)


def _call(client: TestClient, method: str, path: str, headers: dict[str, str] | None = None) -> int:
    kwargs: dict[str, object] = {"headers": headers or {}}
    if method in ("POST", "PUT", "PATCH"):
        kwargs["json"] = {}
    return client.request(method, _url(path), **kwargs).status_code  # type: ignore[arg-type]


def test_the_unauthenticated_surface_is_exactly_the_reviewed_allowlist() -> None:
    public = {f"{m} {r.path}" for r in _routes() if not _needs_principal(r) for m in r.methods}
    assert public == set(PUBLIC), {
        "unreviewed public routes": sorted(public - set(PUBLIC)),
        "allowlisted routes that now need a principal": sorted(set(PUBLIC) - public),
    }


def test_every_protected_route_refuses_anonymous_requests(client: TestClient) -> None:
    wrong = []
    for r in _routes():
        if not _needs_principal(r):
            continue
        for m in r.methods:
            status = _call(client, m, r.path)
            if status != 401:
                wrong.append(f"{m} {r.path} -> {status}")
    assert wrong == []


def test_a_learner_never_succeeds_on_staff_routes(client: TestClient) -> None:
    with get_sessionmaker()() as db:
        learner = Staff(client, db, [], mfa=True)  # MFA too: the role, not the session strength, must decide
    wrong = []
    for r in _routes():
        if not r.path.startswith(STAFF_PREFIXES):
            continue
        for m in r.methods:
            status = _call(client, m, r.path, learner.headers)
            if status < 400 or status >= 500 or status == 401:
                wrong.append(f"{m} {r.path} -> {status}")
    assert wrong == []
