"""P15.S3.T1: size-limited, quarantined screenshots on help requests. Only the isolated worker's re-encoded PNG is
stored and served; owners and scoped staff can view; limits apply; the evidence orphan sweep keeps them."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from portal_api.db import get_sessionmaker
from portal_api.modules.support import service as support
from portal_api.modules.written import service as written
from tests.test_content_workflow import Staff
from tests.test_written_attempts import _png


def _staff(client: TestClient, roles: list[str], scope: dict[str, Any] | None = None) -> Staff:
    with get_sessionmaker()() as db:
        return Staff(client, db, roles, scope)


def _ticket(client: TestClient, who: Staff) -> dict[str, Any]:
    r = client.post(
        "/v1/support/tickets",
        headers=who.headers,
        json={"category": "technical", "subject": "Fixture screenshot", "body": "Fixture: the page shows an error."},
    )
    assert r.status_code == 201, r.text
    return dict(r.json())


def _attach(client: TestClient, who: Staff, ticket_id: str, data: bytes) -> Any:
    return client.post(
        f"/v1/support/tickets/{ticket_id}/attachments",
        headers={**who.headers, "Content-Type": "application/octet-stream"},
        content=data,
    )


def test_a_screenshot_is_re_encoded_and_visible_only_to_owner_and_scoped_staff(client: TestClient) -> None:
    learner, other = _staff(client, []), _staff(client, [])
    support_staff = _staff(client, ["support"])
    reviewer = _staff(client, ["subject_reviewer"], {"grades": [11], "subjects": ["biology"]})
    t = _ticket(client, learner)
    original = _png(seed=4101)
    r = _attach(client, learner, t["id"], original)
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["width"] > 0 and a["height"] > 0
    listed = client.get(f"/v1/support/tickets/{t['id']}", headers=learner.headers).json()["attachments"]
    assert [x["id"] for x in listed] == [a["id"]]
    url = f"/v1/support/tickets/{t['id']}/attachments/{a['id']}"
    mine = client.get(url, headers=learner.headers)
    assert mine.status_code == 200 and mine.headers["content-type"] == "image/png"
    assert mine.headers["x-content-type-options"] == "nosniff" and mine.headers["cache-control"] == "private, no-store"
    assert mine.content.startswith(b"\x89PNG") and mine.content != original  # re-encoded, never the upload itself
    assert client.get(url, headers=other.headers).status_code == 404
    assert client.get(url, headers=support_staff.headers).status_code == 200
    assert client.get(url, headers=reviewer.headers).status_code == 404  # reviewers see only academic reports
    staff_view = client.get(f"/v1/staff/support/tickets/{t['id']}", headers=support_staff.headers).json()
    assert [x["id"] for x in staff_view["attachments"]] == [a["id"]]
    # the evidence store's orphan sweep keeps referenced screenshots
    with get_sessionmaker()() as db:
        written.sweep_orphans(db, older_than_s=0)
    assert client.get(url, headers=learner.headers).status_code == 200


def test_screenshots_are_limited_by_type_size_and_count(client: TestClient) -> None:
    learner = _staff(client, [])
    t = _ticket(client, learner)
    pdf = _attach(client, learner, t["id"], b"%PDF-1.4\n%fixture\n")
    assert pdf.status_code == 422 and pdf.json()["code_reason"] == "SCREENSHOT_REJECTED"
    junk = _attach(client, learner, t["id"], b"not an image at all")
    assert junk.status_code == 422
    big = _attach(client, learner, t["id"], b"\x89PNG\r\n\x1a\n" + b"0" * (support.MAX_SCREENSHOT_BYTES + 1))
    assert big.status_code == 413
    for i in range(support.MAX_ATTACHMENTS_PER_TICKET):
        assert _attach(client, learner, t["id"], _png(seed=4200 + i)).status_code == 201
    over = _attach(client, learner, t["id"], _png(seed=4299))
    assert over.status_code == 409
    other = _staff(client, [])
    assert _attach(client, other, t["id"], _png(seed=4300)).status_code == 404  # not their request


def test_a_resolved_request_takes_no_new_screenshots(client: TestClient) -> None:
    learner, staff = _staff(client, []), _staff(client, ["support"])
    t = _ticket(client, learner)
    client.post(
        f"/v1/staff/support/tickets/{t['id']}/messages",
        headers=staff.headers,
        json={"body": "Fixture: done.", "status": "resolved"},
    )
    assert _attach(client, learner, t["id"], _png(seed=4400)).status_code == 409
