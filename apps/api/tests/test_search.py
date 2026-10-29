"""P11.S2.T3 (SEARCH-01): content search over published lessons as well as chapters and topics.

Lesson text is matched and quoted only where the caller may read the lesson; anyone can find a live lesson by its
title, marked locked. Drafts, unpublished revisions, quarantined or retired lessons, questions, checkpoint answers and
worked-example answers never surface. Equivalent English, Urdu and Roman Urdu terms come from reviewed alias groups:
one person proposes, another approves. Every lesson, term and package here is a labelled technical fixture with
made-up marker words, not academic content."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from portal_api.modules.audit.models import AuditEvent
from portal_api.modules.content.search import LESSON_KINDS, normalise
from tests.test_content_workflow import Staff, _chapter, _confirm_rights, _create, _post, _refs, _save
from tests.test_entitlement_scope import _finance, _grant, _product

BIO11 = {"grades": [11], "subjects": ["biology"]}
URDU_LETTERS = "ابپتٹثجچحخدڈذرڑز"  # sixteen letters: a hex token spelled in Urdu script


def _tok() -> str:
    return uuid.uuid4().hex[:10]


def _urdu(tok: str) -> str:
    return "".join(URDU_LETTERS[int(c, 16)] for c in tok)


def _crew(client: TestClient, db: Session) -> dict[str, Staff]:
    return {
        "author": Staff(client, db, ["content_author"], BIO11),
        "reviewer": Staff(client, db, ["subject_reviewer"], BIO11),
        "publisher": Staff(client, db, ["publisher"], BIO11, mfa=True),
    }


def _lesson(
    client: TestClient, db: Session, crew: dict[str, Staff], title: str, blocks: list[dict[str, Any]]
) -> tuple[dict[str, Any], Any]:
    chapter, doc = _chapter(db, 11, "biology")
    item = _create(client, crew["author"], chapter, title=title)
    saved = _save(client, crew["author"], item, body={"blocks": blocks}, refs=_refs(chapter, doc))
    assert saved.status_code == 200, saved.text
    assert _post(client, crew["author"], item["id"], "submit", {"note": "ready"}).status_code == 200
    _confirm_rights(client, db, doc)
    review = {"decision": "approve", "comment": "Checked fixture"}
    assert _post(client, crew["reviewer"], item["id"], "review", review).status_code == 200
    published = _post(client, crew["publisher"], item["id"], "publish")
    assert published.status_code == 200, published.text
    return published.json(), chapter


def _search(client: TestClient, q: str, who: Staff | None = None, **params: Any) -> dict[str, Any]:
    r = client.get("/v1/search", params={"q": q, "lessons": "true", **params}, headers=who.headers if who else {})
    assert r.status_code == 200, r.text
    return dict(r.json())


def _lesson_hits(result: dict[str, Any], item_id: str) -> list[dict[str, Any]]:
    return [h for h in result["hits"] if h["kind"] == "lesson" and h["id"] == item_id]


def test_lesson_text_is_searched_only_where_the_caller_may_read_it(client: TestClient, db: Session) -> None:
    crew, tok = _crew(client, db), _tok()
    blocks: list[dict[str, Any]] = [
        {"type": "heading", "level": 2, "text": "Fixture heading"},
        {"type": "paragraph", "text": f"Technical fixture paragraph with marker bodyword{tok} in it, not academic."},
        {
            "type": "checkpoint",
            "mode": "question",
            "prompt": f"Fixture prompt secretprompt{tok}",
            "options": [{"id": "a", "text": f"secretoption{tok}"}, {"id": "b", "text": "Other fixture option"}],
            "answer_id": "a",
            "explanation": f"Fixture explanation secretexpl{tok}",
        },
        {
            "type": "example",
            "title": "Fixture example",
            "problem": f"Fixture problem exampleproblem{tok}",
            "steps": ["Fixture step"],
            "answer": f"Fixture answer secretanswer{tok}",
        },
    ]
    item, _ = _lesson(client, db, crew, f"Fixture searchtitle{tok} lesson", blocks)

    # A guest finds the premium lesson by its title only, locked and without a snippet; never by its text.
    guest = _lesson_hits(_search(client, f"searchtitle{tok}"), item["id"])
    assert len(guest) == 1 and guest[0]["locked"] and guest[0]["snippet"] == []
    assert guest[0]["grade"] == 11 and guest[0]["access_tier"] == "premium" and guest[0]["language"] == "en"
    assert _lesson_hits(_search(client, f"bodyword{tok}"), item["id"]) == []
    no_plan = Staff(client, db, [])
    assert _lesson_hits(_search(client, f"bodyword{tok}", no_plan), item["id"]) == []

    # A learner whose plan covers Class 11 Biology finds the text, with a snippet that marks the match.
    learner = Staff(client, db, [])
    assert client.post("/v1/me/trial", headers=learner.headers).status_code == 200
    found = _lesson_hits(_search(client, f"bodyword{tok}", learner), item["id"])
    assert len(found) == 1 and not found[0]["locked"]
    assert {"text": f"bodyword{tok}", "match": True} in found[0]["snippet"]
    assert _lesson_hits(_search(client, f"exampleproblem{tok}", learner), item["id"])
    # Checkpoints and worked-example answers are never searched, so no snippet can give an answer away.
    for secret in ("secretprompt", "secretoption", "secretexpl", "secretanswer"):
        assert _lesson_hits(_search(client, f"{secret}{tok}", learner), item["id"]) == [], secret

    # A package for another subject doesn't open this lesson's text.
    finance = _finance(client, db)
    physics_only = Staff(client, db, [])
    phy = _product(client, finance, "subject_package", {"grades": [11], "subjects": ["physics"]})
    assert _grant(client, finance, physics_only, phy).status_code == 201
    assert _lesson_hits(_search(client, f"bodyword{tok}", physics_only), item["id"]) == []
    assert _lesson_hits(_search(client, f"searchtitle{tok}", physics_only), item["id"])[0]["locked"]

    # Filters: Class 12 never shows a Class 11 lesson; older clients that don't ask for lessons get none.
    assert _lesson_hits(_search(client, f"bodyword{tok}", learner, grade=12), item["id"]) == []
    assert _lesson_hits(_search(client, f"bodyword{tok}", learner, subject="physics"), item["id"]) == []
    old = client.get("/v1/search", params={"q": f"searchtitle{tok}"}, headers=learner.headers)
    assert old.status_code == 200 and old.json()["lessons"] is False
    assert all(h["kind"] in ("chapter", "topic") for h in old.json()["hits"])
    assert old.headers["cache-control"] == "private, no-store"

    # A free preview is readable by everyone, so a guest finds its text too.
    tier = {"tier": "preview", "reason": "Fixture: search preview"}
    assert _post(client, crew["publisher"], item["id"], "access-tier", tier).status_code == 200
    preview = _lesson_hits(_search(client, f"bodyword{tok}"), item["id"])
    assert len(preview) == 1 and not preview[0]["locked"] and preview[0]["snippet"]


def test_only_the_live_published_version_is_searched(client: TestClient, db: Session, physics: dict[str, Any]) -> None:
    crew, tok = _crew(client, db), _tok()
    learner = Staff(client, db, [])
    assert client.post("/v1/me/trial", headers=learner.headers).status_code == 200

    # A draft is never searched, even by its title.
    chapter, doc = _chapter(db, 11, "biology")
    draft = _create(client, crew["author"], chapter, title=f"Fixture drafttitle{tok}")
    body = {"blocks": [{"type": "paragraph", "text": f"Technical fixture draftbody{tok} text."}]}
    assert _save(client, crew["author"], draft, body=body, refs=_refs(chapter, doc)).status_code == 200
    assert _lesson_hits(_search(client, f"drafttitle{tok}", learner), draft["id"]) == []
    assert _lesson_hits(_search(client, f"draftbody{tok}", learner), draft["id"]) == []

    # A revision in progress isn't searched; the published version still is.
    blocks = [{"type": "paragraph", "text": f"Technical fixture liveword{tok} text, not academic."}]
    item, chapter = _lesson(client, db, crew, "Fixture revised lesson", blocks)
    rev = _post(client, crew["author"], item["id"], "revise", {"reason": "Fixture revision for search"})
    assert rev.status_code == 200
    changed = {"blocks": [{"type": "paragraph", "text": f"Technical fixture revisionword{tok} text."}]}
    _, doc = _chapter(db, 11, "biology")
    assert _save(client, crew["author"], rev.json(), body=changed, refs=_refs(chapter, doc)).status_code == 200
    assert _lesson_hits(_search(client, f"revisionword{tok}", learner), item["id"]) == []
    assert _lesson_hits(_search(client, f"liveword{tok}", learner), item["id"])

    # Quarantined and retired lessons disappear from search.
    quarantine = {"reason": "Fixture suspected defect"}
    assert _post(client, crew["publisher"], item["id"], "quarantine", quarantine).status_code == 200
    assert _lesson_hits(_search(client, f"liveword{tok}", learner), item["id"]) == []
    assert _post(client, crew["publisher"], item["id"], "retire", {"reason": "Fixture done"}).status_code == 200
    assert _lesson_hits(_search(client, f"liveword{tok}", learner), item["id"]) == []

    # Questions are never searched, published or not (their keys stay isolated).
    assert LESSON_KINDS == ["lesson"]
    stems = _search(client, "Fixture stem 0", learner, grade=11, subject="physics")
    assert not {h["id"] for h in stems["hits"]} & set(physics["ids"])


def _propose(client: TestClient, who: Staff, forms: list[dict[str, str]], **extra: Any) -> Any:
    body = {"grade": 11, "subject": "biology", "forms": forms, "source_ref": "Fixture: owner glossary TEST-1", **extra}
    return client.post("/v1/studio/search-terms", headers=who.headers, json=body)


def test_alias_groups_need_a_second_person_and_then_widen_search(client: TestClient, db: Session) -> None:
    crew, tok = _crew(client, db), _tok()
    english, roman, urdu = f"aliasenglish{tok}", f"aliasroman{tok}", _urdu(tok)
    blocks = [{"type": "paragraph", "text": f"Technical fixture text that says {roman} only, not academic."}]
    item, _ = _lesson(client, db, crew, "Fixture alias lesson", blocks)
    learner = Staff(client, db, [])
    assert client.post("/v1/me/trial", headers=learner.headers).status_code == 200
    assert _lesson_hits(_search(client, english, learner), item["id"]) == []

    forms = [
        {"language": "en", "text": english.upper()},
        {"language": "roman_ur", "text": roman},
        {"language": "ur", "text": urdu},
    ]
    # Script must match the language, a form can't repeat, and staff outside Class 11 Biology can't propose.
    assert _propose(client, crew["author"], [forms[0], {"language": "ur", "text": "latin"}]).status_code == 422
    assert _propose(client, crew["author"], [forms[0], {"language": "roman_ur", "text": urdu}]).status_code == 422
    assert _propose(client, crew["author"], [forms[0], {"language": "en", "text": english}]).status_code == 422
    outsider = Staff(client, db, ["content_author", "subject_reviewer"], {"grades": [12], "subjects": ["physics"]})
    assert _propose(client, outsider, forms).status_code == 403
    assert _propose(client, crew["reviewer"], forms).status_code == 403  # reviewers approve; authors propose

    proposed = _propose(client, crew["author"], forms)
    assert proposed.status_code == 201, proposed.text
    group = proposed.json()
    assert group["status"] == "proposed" and group["mine"] and not group["can_approve"]
    assert _propose(client, crew["author"], [forms[1], {"language": "en", "text": f"other{tok}"}]).status_code == 409
    # Proposed terms aren't used yet.
    assert _search(client, english, learner)["also_searched"] == []

    approve = f"/v1/studio/search-terms/{group['id']}/approve"
    assert client.post(approve, headers=crew["author"].headers).status_code == 403  # not the proposer
    assert client.post(approve, headers=outsider.headers).status_code == 404
    scope: dict[str, str | int] = {"grade": 11, "subject": "biology"}
    assert client.get("/v1/studio/search-terms", params=scope, headers=learner.headers).status_code == 403
    listed = client.get("/v1/studio/search-terms", params=scope, headers=crew["reviewer"].headers)
    mine = next(g for g in listed.json() if g["id"] == group["id"])
    assert mine["can_approve"] and not mine["mine"]
    approved = client.post(approve, headers=crew["reviewer"].headers)
    assert approved.status_code == 200 and approved.json()["status"] == "approved"

    # Approved: a search in any of the three forms reaches the lesson written with the Roman Urdu one.
    by_english = _search(client, english, learner)
    assert _lesson_hits(by_english, item["id"]) and roman in by_english["also_searched"]
    assert _lesson_hits(_search(client, urdu, learner), item["id"])
    assert _lesson_hits(_search(client, f"what is {english}", learner), item["id"])  # a form inside a longer query
    assert _lesson_hits(_search(client, f"aliasromam{tok}", learner), item["id"])  # a near Roman Urdu spelling
    # Groups belong to one class and subject.
    assert _search(client, english, learner, grade=12)["also_searched"] == []

    retire = f"/v1/studio/search-terms/{group['id']}/retire"
    assert client.post(retire, headers=crew["author"].headers, json={"reason": "Fixture"}).status_code == 403
    retired = client.post(retire, headers=crew["reviewer"].headers, json={"reason": "Fixture: done"})
    assert retired.status_code == 200 and retired.json()["status"] == "retired"
    assert client.post(retire, headers=crew["reviewer"].headers, json={"reason": "Fixture: again"}).status_code == 409
    assert _search(client, english, learner)["also_searched"] == []
    actions = db.scalars(select(AuditEvent.action).where(AuditEvent.target_id == group["id"])).all()
    assert sorted(actions) == ["search_terms.approved", "search_terms.proposed", "search_terms.retired"]


def test_searchable_text_and_query_normalisation(db: Session) -> None:
    body = {
        "blocks": [
            {"type": "paragraph", "text": "Shown"},
            {"type": "checkpoint", "prompt": "Hidden", "options": [], "explanation": "Hidden"},
            {"type": "example", "title": "Shown", "problem": "Shown", "steps": ["Shown"], "answer": "Hidden"},
            {"type": "list", "items": "not a list"},
            7,
        ]
    }
    got = db.execute(text("SELECT lesson_search_text(CAST(:b AS jsonb))"), {"b": json.dumps(body)})
    assert got.scalar_one() == "Shown Shown Shown Shown not a list"
    for odd in ("null", '{"blocks": "x"}', "[]"):  # a malformed draft indexes as nothing instead of failing a save
        assert db.execute(text("SELECT lesson_search_text(CAST(:b AS jsonb))"), {"b": odd}).scalar_one() == ""
    # Urdu words are tokenised as words (this needs a UTF-8 database locale) and folded like queries.
    lexemes = db.execute(
        text("SELECT to_tsvector('english', lesson_search_text(CAST(:b AS jsonb)))::text"),
        {"b": '{"blocks": [{"type": "paragraph", "text": "\\u0643\\u064a\\u0627 \\u0636\\u064e\\u06cc\\u0627"}]}'},
    ).scalar_one()
    assert normalise("كيا") in lexemes and normalise("ضَیا") in lexemes
    assert db.scalar(text("SELECT count(*) FROM pg_indexes WHERE indexname = 'ix_content_version_search'")) == 1
    assert normalise("  Photo-Synthesis,  (LIGHT)! ") == "photo-synthesis light"
    assert normalise("كيا") == "کیا"  # Arabic kaf and yeh fold to the Urdu letters
