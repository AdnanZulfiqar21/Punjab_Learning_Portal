"""W08.S2.T1 (WRITTEN-AUTHZ-01): end-to-end authorisation for written work.

Another learner never reaches someone else's written test through any written route (viewing, uploading, remapping,
transforming, sealing, rechecking, asking for a linked test, reading results), with plausible bodies for the
actions that change work. A reviewer outside the script's class and subject never reaches its case. Page images are
private to shared caches, and no storage key, page id or answer image reaches notifications, logs or someone else's
data export. Scripts, pages and accounts are labelled technical fixtures.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from portal_api.db import get_sessionmaker
from tests.test_authorization_matrix import _routes
from tests.test_written_attempts import _learner, _map, _png, _seal, _start, _upload
from tests.test_written_marking import GOOD, _case_for, _decide, _reviewer

LEARNER_PREFIXES = ("/v1/written-attempts/", "/v1/written/forms/", "/v1/written/linked-forms/")


def _fill(path: str, attempt: dict[str, Any], page: str) -> str:
    return (
        path.replace("{attempt_id}", attempt["id"])
        .replace("{page_id}", page)
        .replace("{position}", "1")
        .replace("{form_id}", str(attempt["form_id"]))
    )


def test_another_learner_and_an_out_of_scope_reviewer_never_reach_written_work(
    client: TestClient, published_written: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    chapter = published_written["chapter"]
    victim, intruder = _learner(client), _learner(client)

    # The victim's sealed, marked and released script, and a second test still open with one page.
    sealed = _start(client, victim, chapter)
    sealed_page = _upload(client, victim, sealed["id"], _png(seed=71)).json()["pages"][0]["id"]
    mapped = _map(client, victim, sealed, {"1:a": {"pages": [sealed_page]}, "1:b": {"unanswered": True}}).json()
    assert _seal(client, victim, sealed["id"], mapped["manifest_revision"]).status_code == 200
    reviewer = _reviewer(client)
    case = _case_for(client, reviewer, sealed["id"])
    client.post(f"/v1/studio/written/cases/{case['id']}/lease", headers=reviewer.headers)
    assert _decide(client, reviewer, case["id"], 0, GOOD, release=True).status_code == 200
    active = _start(client, victim, chapter)
    active_page = _upload(client, victim, active["id"], _png(seed=72)).json()["pages"][0]["id"]

    # Every learner-owned written route, as another learner: never success, never the victim's data.
    leaked = []
    for route in _routes():
        if not route.path.startswith(LEARNER_PREFIXES):
            continue
        for attempt, page in ((sealed, sealed_page), (active, active_page)):
            url = _fill(route.path, attempt, page)
            for method in route.methods:
                r = client.request(method, url, headers=intruder.headers, json={} if method != "GET" else None)
                if r.status_code < 400 or (method == "GET" and r.status_code not in (403, 404)):
                    leaked.append(f"{method} {route.path} -> {r.status_code}")
                if page in r.text:
                    leaked.append(f"{method} {route.path} echoed a page id")
    assert leaked == []

    # With plausible bodies, the actions that change work are still refused as not found.
    attempt_url = f"/v1/written-attempts/{active['id']}"
    changes = {
        "upload": _upload(client, intruder, active["id"], _png(seed=73)),
        "remap": _map(client, intruder, active, {"1:a": {"unanswered": True}, "1:b": {"unanswered": True}}),
        "transform": client.put(
            f"{attempt_url}/pages/{active_page}/transform", headers=intruder.headers, json={"rotate": 90}
        ),
        "seal": _seal(client, intruder, active["id"], 1),
        "recheck": client.post(
            f"/v1/written-attempts/{sealed['id']}/recheck",
            headers=intruder.headers,
            json={"reason": "Fixture: I disagree with this mark", "positions": [1]},
        ),
        "linked test": client.post(
            f"/v1/written-attempts/{sealed['id']}/linked-forms",
            headers={**intruder.headers, "Idempotency-Key": "fixture-linked-key-1"},
            json={"reason": "REWRITE", "positions": [1]},
        ),
        "start their test": client.post(f"/v1/written/forms/{active['form_id']}/attempt", headers=intruder.headers),
    }
    assert {k: r.status_code for k, r in changes.items()} == {k: 404 for k in changes}
    still = client.get(attempt_url, headers=victim.headers).json()
    assert [p["id"] for p in still["pages"]] == [active_page]  # nothing changed

    # A reviewer for another class and subject never reaches the case or its pages.
    outsider = _reviewer(client, 11, "physics")
    staff_calls = [
        client.get(f"/v1/studio/written/cases/{case['id']}", headers=outsider.headers),
        client.post(f"/v1/studio/written/cases/{case['id']}/lease", headers=outsider.headers),
        client.get(f"/v1/studio/written/cases/{case['id']}/pages/{sealed_page}", headers=outsider.headers),
        client.get(f"/v1/studio/written/cases/{case['id']}/pages/{sealed_page}/detail", headers=outsider.headers),
        _decide(client, outsider, case["id"], 1, GOOD, release=True),
    ]
    assert [r.status_code for r in staff_calls if r.status_code not in (403, 404)] == []

    # Page images stay out of shared caches; storage keys, page ids and images stay out of notifications, logs and
    # another learner's export.
    image = client.get(f"/v1/written-attempts/{sealed['id']}/pages/{sealed_page}", headers=victim.headers)
    assert image.status_code == 200 and "no-store" in image.headers["cache-control"]
    assert "private" in image.headers["cache-control"]
    with get_sessionmaker()() as db:
        keys = list(
            db.execute(
                text("select storage_key from written_file where attempt_id = any(:a)"),
                {"a": [sealed["id"], active["id"]]},
            ).scalars()
        )
        notes = db.execute(
            text("select params::text || title || body || coalesce(link, '') from notification where user_id = :u"),
            {"u": str(victim.id)},
        ).scalars()
        sent = " ".join(notes)
    assert keys and sent  # the files exist and the release was notified
    for secret in (*keys, sealed_page, active_page):
        assert secret not in sent, "a notification carries a storage key or page id"
    # The application's own log records, with their structured fields: never a storage key. (Ids in request paths
    # identify objects; they aren't answer content.)
    app_logs = " ".join(json.dumps(r.__dict__, default=str) for r in caplog.records if r.name.startswith("portal"))
    assert app_logs and not [k for k in keys if k in app_logs], "a log record carries a storage key"
    export = client.get("/v1/me/data-export", headers=intruder.headers)
    assert export.status_code == 200
    dumped = json.dumps(json.loads(export.content))
    assert sealed["id"] not in dumped and active["id"] not in dumped
