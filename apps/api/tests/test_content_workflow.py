"""Editorial workflow (P06): scope, independent review, optimistic autosave, source references, publication gates,
revisions, quarantine and retirement. Lesson bodies here are technical fixtures that exercise the software; they are
not academic content and are never published outside this test database."""

from __future__ import annotations

import time
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from portal_api.modules.curriculum.importer import DEFAULT_CATALOGUE, DEFAULT_REGISTRY, run_import
from portal_api.modules.curriculum.models import BookEdition, Chapter, Grade, SourceDocument, Subject
from portal_api.modules.identity.models import AppUser, StaffRoleGrant

FIXTURE_BODY: dict[str, Any] = {
    "blocks": [
        {"type": "heading", "level": 2, "text": "Fixture heading"},
        {"type": "paragraph", "text": "Technical fixture paragraph used only to exercise the workflow."},
    ]
}


class Staff:
    def __init__(
        self, client: TestClient, db: Session, roles: list[str], scope: dict[str, Any] | None = None, mfa: bool = False
    ) -> None:
        self.email = f"staff-{uuid.uuid4().hex[:10]}@example.com"
        r = client.post("/v1/dev-auth/register", json={"email": self.email, "password": "correct-horse-battery"})
        assert r.status_code == 202
        self._client, self._mfa, self._issued = client, mfa, 0.0
        me = client.get("/v1/me", headers=self.headers)
        assert me.status_code == 200
        self.id = uuid.UUID(me.json()["id"])
        for role in roles:
            db.add(StaffRoleGrant(user_id=self.id, role=role, scope=scope or {}, reason="test fixture"))
        db.commit()

    @property
    def headers(self) -> dict[str, str]:
        """A bearer token, re-issued after ten minutes or after the dev issuer was replaced (`test_dev_issuer_race`
        resets it): session-scoped fixtures outlive both the 15-minute dev token and the issuer's keys."""
        from portal_api.modules.identity import tokens

        issuer = tokens.get_dev_issuer()
        if time.monotonic() - self._issued > 600 or getattr(self, "_issuer", None) is not issuer:
            self._issuer = issuer
            tok = self._client.post(
                "/v1/dev-auth/token",
                json={"email": self.email, "password": "correct-horse-battery", "mfa": self._mfa},
            )
            assert tok.status_code == 200, tok.text
            self._headers = {"Authorization": f"Bearer {tok.json()['access_token']}"}
            self._issued = time.monotonic()
        return self._headers


def _chapter(db: Session, grade: int, subject: str, index: int = 0) -> tuple[Chapter, SourceDocument]:
    chapters = db.scalars(
        select(Chapter)
        .join(BookEdition, BookEdition.id == Chapter.book_id)
        .join(Grade, Grade.id == BookEdition.grade_id)
        .join(Subject, Subject.id == BookEdition.subject_id)
        .where(
            Grade.number == grade, Subject.code == subject, Chapter.retired_at.is_(None), Chapter.pdf_start.is_not(None)
        )
        .order_by(Chapter.display_order)
    ).all()
    chapter = chapters[index]
    book = db.get(BookEdition, chapter.book_id)
    assert book is not None
    doc = db.get(SourceDocument, book.source_document_id)
    assert doc is not None
    return chapter, doc


def _refs(chapter: Chapter, doc: SourceDocument) -> list[dict[str, Any]]:
    assert chapter.pdf_start is not None
    return [{"source_document_id": str(doc.id), "pdf_from": chapter.pdf_start, "pdf_to": chapter.pdf_start + 1}]


def _create(client: TestClient, author: Staff, chapter: Chapter, title: str = "Fixture lesson") -> dict[str, Any]:
    r = client.post("/v1/studio/items", headers=author.headers, json={"chapter_id": str(chapter.id), "title": title})
    assert r.status_code == 201, r.text
    return dict(r.json())


def _save(
    client: TestClient,
    who: Staff,
    item: dict[str, Any],
    body: dict[str, Any] | None = None,
    refs: list[dict[str, Any]] | None = None,
    revision: int | None = None,
) -> Any:
    return client.put(
        f"/v1/studio/items/{item['id']}/draft",
        headers=who.headers,
        json={
            "revision": revision if revision is not None else item["working"]["revision"],
            "body": body or FIXTURE_BODY,
            "source_refs": refs or [],
        },
    )


def _post(client: TestClient, who: Staff, item_id: str, action: str, json: dict[str, Any] | None = None) -> Any:
    return client.post(f"/v1/studio/items/{item_id}/{action}", headers=who.headers, json=json or {})


def _confirm_rights(client: TestClient, db: Session, doc: SourceDocument) -> None:
    owner = Staff(client, db, ["owner_admin"], mfa=True)
    r = client.put(
        f"/v1/studio/sources/{doc.id}/publication-rights",
        headers=owner.headers,
        json={"rights": "CONFIRMED", "evidence": "Test fixture: owner decision record TEST-1"},
    )
    # The owner has no content role, so the studio dependency isn't involved; the rights permission is enough.
    assert r.status_code == 200, r.text


@pytest.fixture
def team(client: TestClient, db: Session) -> dict[str, Staff]:
    bio11 = {"grades": [11], "subjects": ["biology"]}
    return {
        "author": Staff(client, db, ["content_author"], bio11),
        "author2": Staff(client, db, ["content_author"], bio11),
        "reviewer": Staff(client, db, ["subject_reviewer"], bio11),
        "publisher": Staff(client, db, ["publisher"], bio11, mfa=True),
        "publisher_no_mfa": Staff(client, db, ["publisher"], bio11),
        "outsider": Staff(
            client, db, ["content_author", "subject_reviewer"], {"grades": [12], "subjects": ["physics"]}
        ),
        "student": Staff(client, db, []),
    }


# ------------------------------------------------------------------ access and scope
def test_studio_is_staff_only_and_scoped(client: TestClient, db: Session, team: dict[str, Staff]) -> None:
    chapter, _ = _chapter(db, 11, "biology")
    assert client.get("/v1/studio/queue", headers=team["student"].headers).status_code == 403
    assert client.get("/v1/studio/queue").status_code == 401
    r = client.post(
        "/v1/studio/items",
        headers=team["outsider"].headers,
        json={"chapter_id": str(chapter.id), "title": "Out of scope"},
    )
    assert r.status_code == 403
    item = _create(client, team["author"], chapter)
    # Items outside a person's scope are invisible, not just read-only.
    assert client.get(f"/v1/studio/items/{item['id']}", headers=team["outsider"].headers).status_code == 404
    ids = [i["id"] for i in client.get("/v1/studio/queue", headers=team["outsider"].headers).json()]
    assert item["id"] not in ids
    assert item["id"] in [i["id"] for i in client.get("/v1/studio/queue", headers=team["reviewer"].headers).json()]
    assert item["state"] == "draft" and item["availability"] == "unpublished"
    assert item["actions"]["edit"] and not item["actions"]["publish"]


# ------------------------------------------------------------------ autosave and validation
def test_autosave_detects_concurrent_edits(client: TestClient, db: Session, team: dict[str, Staff]) -> None:
    chapter, doc = _chapter(db, 11, "biology")
    item = _create(client, team["author"], chapter)
    first = _save(client, team["author"], item, refs=_refs(chapter, doc))
    assert first.status_code == 200, first.text
    assert first.json()["working"]["revision"] == 2
    # A second editor still holding revision 1 must not overwrite the first editor's work.
    stale = _save(client, team["author2"], item, body={"blocks": [{"type": "paragraph", "text": "Other"}]}, revision=1)
    assert stale.status_code == 409
    problem = stale.json()
    assert problem["current"]["revision"] == 2 and problem["current"]["updated_by"] == team["author"].email
    assert problem["current"]["body"]["blocks"][0]["text"] == "Fixture heading"
    # After reviewing the current text the second editor saves on top of it and becomes a contributor.
    ok = _save(client, team["author2"], item, revision=2, refs=_refs(chapter, doc))
    assert ok.status_code == 200
    assert set(ok.json()["working"]["contributors"]) == {team["author"].email, team["author2"].email}


def test_block_schema_and_source_references_are_validated(
    client: TestClient, db: Session, team: dict[str, Staff]
) -> None:
    chapter, doc = _chapter(db, 11, "biology")
    _, other_doc = _chapter(db, 11, "chemistry")
    item = _create(client, team["author"], chapter)
    bad_block = _save(client, team["author"], item, body={"blocks": [{"type": "video", "url": "x"}]})
    assert bad_block.status_code == 422 and bad_block.json()["errors"]
    unknown_field = _save(
        client, team["author"], item, body={"blocks": [{"type": "paragraph", "text": "x", "html": "<b>"}]}
    )
    assert unknown_field.status_code == 422
    wrong_book = _save(client, team["author"], item, refs=_refs(chapter, other_doc))
    assert wrong_book.status_code == 422 and "own textbook" in wrong_book.json()["errors"][0]
    beyond = _save(
        client,
        team["author"],
        item,
        refs=[{"source_document_id": str(doc.id), "pdf_from": 1, "pdf_to": doc.pdf_pages + 5}],
    )
    assert beyond.status_code == 422
    # Submission needs at least one source page reference.
    saved = _save(client, team["author"], item)
    assert saved.status_code == 200
    no_refs = _post(client, team["author"], item["id"], "submit")
    assert no_refs.status_code == 422 and any("source page" in e for e in no_refs.json()["errors"])


# ------------------------------------------------------------------ review and publication
def _submitted(
    client: TestClient,
    db: Session,
    team: dict[str, Staff],
    subject: str = "biology",
    body: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], Chapter, SourceDocument]:
    chapter, doc = _chapter(db, 11, subject)
    item = _create(client, team["author"], chapter)
    saved = _save(client, team["author"], item, body=body, refs=_refs(chapter, doc))
    assert saved.status_code == 200, saved.text
    sub = _post(client, team["author"], item["id"], "submit", {"note": "ready"})
    assert sub.status_code == 200, sub.text
    assert sub.json()["state"] == "submitted"
    return sub.json(), chapter, doc


def test_independent_review_is_enforced(client: TestClient, db: Session, team: dict[str, Staff]) -> None:
    # An author who also holds a reviewer role still can't approve a version they edited.
    dual = Staff(client, db, ["content_author", "subject_reviewer"], {"grades": [11], "subjects": ["biology"]})
    chapter, doc = _chapter(db, 11, "biology")
    item = _create(client, dual, chapter)
    _save(client, dual, item, refs=_refs(chapter, doc))
    assert _post(client, dual, item["id"], "submit").status_code == 200
    own = _post(client, dual, item["id"], "review", {"decision": "approve", "comment": "Looks fine"})
    assert own.status_code == 403 and "Independent review" in own.json()["detail"]
    # Reviewers outside the subject/class scope can't review either.
    outsider = _post(client, team["outsider"], item["id"], "review", {"decision": "approve", "comment": "ok ok"})
    assert outsider.status_code == 403
    approved = _post(client, team["reviewer"], item["id"], "review", {"decision": "approve", "comment": "Checked"})
    assert approved.status_code == 200 and approved.json()["state"] == "approved"
    assert approved.json()["working"]["approved_by"] == team["reviewer"].email


def test_changes_requested_cycle(client: TestClient, db: Session, team: dict[str, Staff]) -> None:
    item, chapter, doc = _submitted(client, db, team)
    # Submitted versions are frozen.
    assert _save(client, team["author"], item, refs=_refs(chapter, doc)).status_code == 409
    r = _post(
        client,
        team["reviewer"],
        item["id"],
        "review",
        {"decision": "request_changes", "comment": "Clarify the second paragraph."},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "changes_requested" and body["open_feedback"] == 1
    assert body["working"]["reviews"][0]["comment"] == "Clarify the second paragraph."
    edited = _save(client, team["author"], body, refs=_refs(chapter, doc))
    assert edited.status_code == 200 and edited.json()["state"] == "draft"
    assert _post(client, team["author"], item["id"], "submit").json()["state"] == "submitted"
    withdrawn = _post(client, team["author"], item["id"], "withdraw")
    assert withdrawn.json()["state"] == "draft"


def test_publication_needs_mfa_independence_and_confirmed_rights(
    client: TestClient, db: Session, team: dict[str, Staff]
) -> None:
    # Chemistry rights stay UNVERIFIED in this test database.
    chem = {"grades": [11], "subjects": ["chemistry"]}
    author = Staff(client, db, ["content_author"], chem)
    reviewer = Staff(client, db, ["subject_reviewer"], chem)
    publisher = Staff(client, db, ["publisher"], chem, mfa=True)
    publisher_no_mfa = Staff(client, db, ["publisher"], chem)
    local = {"author": author}
    item, _, doc = _submitted(client, db, local, subject="chemistry")
    assert doc.publication_rights == "UNVERIFIED"
    pending = client.get(f"/v1/studio/items/{item['id']}", headers=author.headers).json()
    assert not any("B01" in b for b in pending["blockers"])  # a scoped chemistry reviewer exists
    assert (
        _post(client, reviewer, item["id"], "review", {"decision": "approve", "comment": "Checked"}).status_code == 200
    )
    assert _post(client, publisher_no_mfa, item["id"], "publish").status_code == 403
    blocked = _post(client, publisher, item["id"], "publish")
    assert blocked.status_code == 422
    assert any("Publication rights" in e and "UNVERIFIED" in e for e in blocked.json()["errors"])
    detail = client.get(f"/v1/studio/items/{item['id']}", headers=publisher.headers).json()
    assert detail["state"] == "approved" and any("Publication rights" in b for b in detail["blockers"])
    assert client.get(f"/v1/chapters/{item['chapter_id']}/lessons").json() == []


def test_missing_reviewer_is_reported_as_a_blocker(client: TestClient, db: Session) -> None:
    math12 = {"grades": [12], "subjects": ["mathematics"]}
    author = Staff(client, db, ["content_author"], math12)
    chapter, doc = _chapter(db, 12, "mathematics")
    item = _create(client, author, chapter)
    _save(client, author, item, refs=_refs(chapter, doc))
    sub = _post(client, author, item["id"], "submit")
    assert sub.status_code == 200
    # OCT9-05: other modules may already have created reviewers covering this scope (e.g. unscoped ones), so the
    # zero-reviewer path is checked in a transaction that sees no reviewers and is then rolled back.
    from portal_api.modules.content.models import ContentItem
    from portal_api.modules.content.router import _eligible_reviewers

    row = db.get(ContentItem, uuid.UUID(item["id"]))
    assert row is not None
    db.execute(text("update staff_role_grant set revoked_at = now()"))  # any role that can review; rolled back
    assert _eligible_reviewers(db, row) == 0
    db.rollback()
    reported = any("B01" in b for b in sub.json()["blockers"])  # stays private in review; nothing is invented
    assert reported == (_eligible_reviewers(db, row) == 0)
    Staff(client, db, ["subject_reviewer"], math12)
    again = client.get(f"/v1/studio/items/{item['id']}", headers=author.headers).json()
    assert not any("B01" in b for b in again["blockers"])


def test_full_lifecycle_publish_revise_quarantine_retire(
    client: TestClient, db: Session, team: dict[str, Staff]
) -> None:
    item, chapter, doc = _submitted(client, db, team)
    _confirm_rights(client, db, doc)
    assert (
        _post(
            client,
            team["reviewer"],
            item["id"],
            "review",
            {"decision": "approve", "comment": "Checked against source pages"},
        ).status_code
        == 200
    )
    published = _post(client, team["publisher"], item["id"], "publish")
    assert published.status_code == 200, published.text
    assert published.json()["state"] == "published" and published.json()["availability"] == "live"
    lessons = client.get(f"/v1/chapters/{chapter.id}/lessons").json()
    assert [(lesson["id"], lesson["version"]) for lesson in lessons if lesson["id"] == item["id"]] == [(item["id"], 1)]
    # R07: premium by default, so an anonymous reader sees the title only until a publisher marks a preview.
    mine = next(x for x in lessons if x["id"] == item["id"])
    assert mine["locked"] and mine["body"] is None and mine["access_tier"] == "premium"
    tier = _post(client, team["publisher"], item["id"], "access-tier", {"tier": "preview", "reason": "Fixture preview"})
    assert tier.status_code == 200 and tier.json()["access_tier"] == "preview"

    # A revision needs a reason; learners keep seeing version 1 until version 2 is published.
    assert _post(client, team["author"], item["id"], "revise", {"reason": "x"}).status_code == 422
    rev = _post(client, team["author"], item["id"], "revise", {"reason": "Correct a fixture typo"})
    assert rev.status_code == 200 and rev.json()["working_version"] == 2 and rev.json()["published_version"] == 1
    assert rev.json()["availability"] == "live"
    changed = {"blocks": [*FIXTURE_BODY["blocks"], {"type": "list", "items": ["one", "two"]}]}
    saved = _save(client, team["author"], rev.json(), body=changed, refs=_refs(chapter, doc))
    assert saved.status_code == 200
    v1 = next(x for x in client.get(f"/v1/chapters/{chapter.id}/lessons").json() if x["id"] == item["id"])
    assert v1["version"] == 1 and len(v1["body"]["blocks"]) == 2

    # Quarantine hides the live version while the correction goes through review.
    q = _post(client, team["publisher"], item["id"], "quarantine", {"reason": "Suspected fixture defect"})
    assert q.status_code == 200 and q.json()["availability"] == "quarantined"
    assert item["id"] not in [x["id"] for x in client.get(f"/v1/chapters/{chapter.id}/lessons").json()]
    assert _post(client, team["author"], item["id"], "submit").status_code == 200
    assert (
        _post(client, team["reviewer"], item["id"], "review", {"decision": "approve", "comment": "Fixed"}).status_code
        == 200
    )
    v2 = _post(client, team["publisher"], item["id"], "publish")
    assert v2.status_code == 200 and v2.json()["availability"] == "live" and v2.json()["published_version"] == 2
    live = [x for x in client.get(f"/v1/chapters/{chapter.id}/lessons").json() if x["id"] == item["id"]]
    assert live[0]["version"] == 2 and len(live[0]["body"]["blocks"]) == 3

    # Quarantine and release without a new version.
    _post(client, team["publisher"], item["id"], "quarantine", {"reason": "Second check"})
    rel = _post(client, team["publisher"], item["id"], "release", {"reason": "Not a defect"})
    assert rel.json()["availability"] == "live"

    retired = _post(client, team["publisher"], item["id"], "retire", {"reason": "Fixture no longer needed"})
    assert retired.status_code == 200 and retired.json()["availability"] == "retired"
    assert item["id"] not in [x["id"] for x in client.get(f"/v1/chapters/{chapter.id}/lessons").json()]
    assert _post(client, team["author"], item["id"], "revise", {"reason": "Try again later"}).status_code == 409

    history = client.get(f"/v1/studio/items/{item['id']}/history", headers=team["reviewer"].headers).json()
    actions = [h["action"] for h in history]
    assert actions == [
        "content.created",
        "content.submitted",
        "content.approved",
        "content.published",
        "content.access_tier_changed",
        "content.revision_started",
        "content.quarantined",
        "content.submitted",
        "content.approved",
        "content.published",
        "content.quarantined",
        "content.released",
        "content.retired",
    ]
    assert history[9]["details"]["resolved_quarantine"] is True and history[9]["details"]["superseded"] == 1


def test_publisher_who_edited_cannot_publish(client: TestClient, db: Session, team: dict[str, Staff]) -> None:
    bio11 = {"grades": [11], "subjects": ["biology"]}
    hybrid = Staff(client, db, ["content_author", "publisher"], bio11, mfa=True)
    chapter, doc = _chapter(db, 11, "biology", 1)
    item = _create(client, hybrid, chapter)
    _save(client, hybrid, item, refs=_refs(chapter, doc))
    _post(client, hybrid, item["id"], "submit")
    _post(
        client,
        team["reviewer"],
        item["id"],
        "review",
        {"decision": "approve", "comment": "Checked against source pages"},
    )
    r = _post(client, hybrid, item["id"], "publish")
    assert r.status_code == 403


def test_unrenderable_blocks_need_a_reviewed_fallback(client: TestClient, db: Session, team: dict[str, Staff]) -> None:
    eq = {"blocks": [{"type": "equation", "latex": "E = mc^2", "text_alt": "E equals m c squared"}]}
    item, _, doc = _submitted(client, db, team, body=eq)
    _confirm_rights(client, db, doc)
    _post(
        client,
        team["reviewer"],
        item["id"],
        "review",
        {"decision": "approve", "comment": "Checked against source pages"},
    )
    r = _post(client, team["publisher"], item["id"], "publish")
    assert r.status_code == 422 and any("reviewed fallback" in e for e in r.json()["errors"])
    reg = client.get("/v1/studio/block-registry", headers=team["author"].headers).json()
    assert reg["content_schema_version"] == 1
    assert {b["type"] for b in reg["blocks"]} >= {"paragraph", "equation"}


def test_publication_rights_survive_reimport(client: TestClient, db: Session) -> None:
    owner = Staff(client, db, ["owner_admin"], mfa=True)
    owner_no_mfa = Staff(client, db, ["owner_admin"])
    _, doc = _chapter(db, 12, "computer_science")
    url = f"/v1/studio/sources/{doc.id}/publication-rights"
    body = {"rights": "CONFIRMED", "evidence": "Test fixture: owner decision record TEST-2"}
    assert client.put(url, headers=owner_no_mfa.headers, json=body).status_code == 403
    assert client.put(url, headers=owner.headers, json=body).status_code == 200
    batch = run_import(db, DEFAULT_CATALOGUE, DEFAULT_REGISTRY, apply=True)
    assert batch.status == "APPLIED"
    db.expire_all()
    fresh = db.get(SourceDocument, doc.id)
    assert fresh is not None and fresh.publication_rights == "CONFIRMED"
    assert fresh.publication_rights_evidence == "Test fixture: owner decision record TEST-2"
    who = db.get(AppUser, fresh.publication_rights_set_by)
    assert who is not None and who.email == owner.email


def test_queue_scope_is_applied_before_the_limit(client: TestClient, db: Session) -> None:
    bio = Staff(client, db, ["content_author"], {"grades": [11], "subjects": ["biology"]})
    chem = Staff(client, db, ["content_author"], {"grades": [11], "subjects": ["chemistry"]})
    bio_chapter, _ = _chapter(db, 11, "biology")
    chem_chapter, _ = _chapter(db, 11, "chemistry")
    mine = _create(client, bio, bio_chapter, "Scoped item")
    for i in range(3):  # newer items outside the biology author's scope must not crowd it out of a small page
        _create(client, chem, chem_chapter, f"Other scope {i}")
    page = client.get("/v1/studio/queue?limit=1", headers=bio.headers).json()
    assert [i["id"] for i in page] == [mine["id"]]
