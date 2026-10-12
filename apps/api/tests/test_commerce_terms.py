"""P14.S1.T3 (PRICING-01): purchase terms are owner-reviewed text, not code. One finance person drafts a version and a
different one publishes it; publishing supersedes the previous version and every version is kept; the public route
shows only the published version. The wording here is a labelled technical fixture, not real terms."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.test_content_workflow import Staff


def _terms(tag: str) -> dict[str, Any]:
    return {
        "tax_note": f"[FIXTURE {tag}] Tax treatment wording for a test.",
        "renewal_note": f"[FIXTURE {tag}] Renewal wording for a test.",
        "conversion_note": f"[FIXTURE {tag}] Early conversion wording for a test.",
        "refund_note": f"[FIXTURE {tag}] Refund wording for a test.",
    }


def test_terms_need_two_people_and_keep_every_version(client: TestClient, db: Session) -> None:
    drafter = Staff(client, db, ["finance"], None, mfa=True)
    publisher = Staff(client, db, ["finance"], None, mfa=True)
    author = Staff(client, db, ["content_author"], {"grades": [11], "subjects": ["biology"]})
    before = client.get("/v1/commerce-terms")
    assert before.status_code == 200 and before.headers["cache-control"].startswith("public")
    previous = before.json()["published"]

    assert client.put("/v1/admin/commerce-terms/draft", headers=author.headers, json=_terms("a")).status_code == 403
    short = {**_terms("a"), "tax_note": "too short"}
    assert client.put("/v1/admin/commerce-terms/draft", headers=drafter.headers, json=short).status_code == 422
    draft = client.put("/v1/admin/commerce-terms/draft", headers=drafter.headers, json=_terms("a"))
    assert draft.status_code == 200 and draft.json()["draft_is_mine"] is True
    assert client.get("/v1/commerce-terms").json()["published"] == previous  # a draft is never public
    other = client.put("/v1/admin/commerce-terms/draft", headers=publisher.headers, json=_terms("b"))
    assert other.status_code == 409  # one open draft, changed only by its author

    reason = {"reason": "Fixture: owner reviewed the wording"}
    own = client.post("/v1/admin/commerce-terms/publish", headers=drafter.headers, json=reason)
    assert own.status_code == 409 and own.json()["code_reason"] == "TWO_PEOPLE"
    done = client.post("/v1/admin/commerce-terms/publish", headers=publisher.headers, json=reason)
    assert done.status_code == 200 and done.json()["draft"] is None
    public = client.get("/v1/commerce-terms").json()["published"]
    assert public["tax_note"] == _terms("a")["tax_note"] and public["status"] == "published"

    client.put("/v1/admin/commerce-terms/draft", headers=publisher.headers, json=_terms("c"))
    client.post("/v1/admin/commerce-terms/publish", headers=drafter.headers, json=reason)
    newer = client.get("/v1/commerce-terms").json()["published"]
    assert newer["version"] == public["version"] + 1 and newer["refund_note"] == _terms("c")["refund_note"]
    statuses = (
        db.execute(
            text("select status from commerce_terms where version in (:a, :b) order by version"),
            {"a": public["version"], "b": newer["version"]},
        )
        .scalars()
        .all()
    )
    assert statuses == ["superseded", "published"]  # the earlier wording is kept, never overwritten
