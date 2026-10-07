"""MCQ items on the editorial workflow (P08.S1/S2): schema, submission rules, review checklist, families, quarantine
levels and answer-key isolation. Question text here is a technical fixture, never academic content."""

from __future__ import annotations

import copy
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.test_content_workflow import Staff, _chapter, _confirm_rights, _post, _refs

CHECKS = {c: True for c in ("accuracy", "ambiguity", "units", "diagrams", "grammar", "mapping")}


def _p(text: str) -> list[dict[str, Any]]:
    return [{"type": "paragraph", "text": text}]


VALID: dict[str, Any] = {
    "stem": _p("Fixture stem: which option is the fixture answer?"),
    "options": [
        {"id": "o1", "blocks": _p("Fixture option one")},
        {"id": "o2", "blocks": _p("Fixture option two")},
        {"id": "o3", "blocks": _p("Fixture option three")},
        {"id": "o4", "blocks": _p("Fixture option four")},
    ],
    "correct_option_id": "o2",
    "explanation": {
        "correct": _p("Fixture reasoning for the correct option."),
        "distractors": {"o1": "Fixture note one", "o3": "Fixture note three", "o4": "Fixture note four"},
    },
    "metadata": {"difficulty": "medium", "estimated_seconds": 60, "cognitive_demand": "apply"},
}


@pytest.fixture
def bio(client: TestClient, db: Session) -> dict[str, Staff]:
    scope = {"grades": [11], "subjects": ["biology"]}
    return {
        "author": Staff(client, db, ["content_author"], scope),
        "reviewer": Staff(client, db, ["subject_reviewer"], scope),
        "publisher": Staff(client, db, ["publisher"], scope, mfa=True),
    }


def _new_mcq(client: TestClient, author: Staff, chapter_id: str, **extra: Any) -> dict[str, Any]:
    r = client.post(
        "/v1/studio/items",
        headers=author.headers,
        json={"kind": "mcq", "chapter_id": chapter_id, "title": "Fixture question", **extra},
    )
    assert r.status_code == 201, r.text
    return dict(r.json())


def _save(client: TestClient, who: Staff, item: dict[str, Any], body: dict[str, Any], refs: list[Any]) -> Any:
    return client.put(
        f"/v1/studio/items/{item['id']}/draft",
        headers=who.headers,
        json={"revision": item["working"]["revision"], "body": body, "source_refs": refs},
    )


def test_new_question_starts_as_an_incomplete_private_draft(
    client: TestClient, db: Session, bio: dict[str, Staff]
) -> None:
    chapter, doc = _chapter(db, 11, "biology")
    item = _new_mcq(client, bio["author"], str(chapter.id))
    assert item["kind"] == "mcq" and item["family_id"] == item["id"]
    assert [o["id"] for o in item["working"]["body"]["options"]] == ["o1", "o2", "o3", "o4"]
    assert item["review_checklist"] == list(CHECKS) and item["quarantine_levels"] == ["SOFT", "VOID", "KEY_ERROR"]
    # Drafts may be incomplete…
    partial = _save(client, bio["author"], item, {"stem": _p("Half-written fixture stem")}, _refs(chapter, doc))
    assert partial.status_code == 200, partial.text
    # …but submission lists everything that is missing.
    r = _post(client, bio["author"], item["id"], "submit")
    assert r.status_code == 422
    errors = " ".join(r.json()["errors"])
    for expected in ("options", "correct option", "Explain why"):
        assert expected in errors


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda b: b["options"][2].update(blocks=_p("Fixture option two")), "duplicates another option"),
        (lambda b: b.update(correct_option_id="o9"), "must be one of the options"),
        (lambda b: b["options"].append({"id": "o1", "blocks": _p("Another")}), "unique"),
        (lambda b: b.update(origin="authorised_past_paper"), "Past-paper questions need"),
        (lambda b: b["explanation"]["distractors"].update(o2="Note on the key"), "correct option can't have"),
        (lambda b: b["explanation"].update(correct=[]), "Explain why"),
    ],
)
def test_submission_rules(client: TestClient, db: Session, bio: dict[str, Staff], mutate: Any, message: str) -> None:
    chapter, doc = _chapter(db, 11, "biology")
    item = _new_mcq(client, bio["author"], str(chapter.id))
    body = copy.deepcopy(VALID)
    mutate(body)
    assert _save(client, bio["author"], item, body, _refs(chapter, doc)).status_code == 200
    r = _post(client, bio["author"], item["id"], "submit")
    assert r.status_code == 422 and message in " ".join(r.json()["errors"]), r.json()


def test_dependent_options_warn_against_shuffling(client: TestClient, db: Session, bio: dict[str, Staff]) -> None:
    chapter, doc = _chapter(db, 11, "biology")
    item = _new_mcq(client, bio["author"], str(chapter.id))
    body = copy.deepcopy(VALID)
    body["options"][3]["blocks"] = _p("All of the above")
    _save(client, bio["author"], item, body, _refs(chapter, doc))
    v = client.post(
        "/v1/studio/validate",
        headers=bio["author"].headers,
        json={"kind": "mcq", "chapter_id": str(chapter.id), "body": body, "source_refs": _refs(chapter, doc)},
    ).json()
    assert v["ok"] and any("turn off shuffling" in w for w in v["warnings"])


def test_review_checklist_publication_and_key_isolation(client: TestClient, db: Session, bio: dict[str, Staff]) -> None:
    chapter, doc = _chapter(db, 11, "biology")
    item = _new_mcq(client, bio["author"], str(chapter.id))
    assert _save(client, bio["author"], item, VALID, _refs(chapter, doc)).status_code == 200
    assert _post(client, bio["author"], item["id"], "submit").status_code == 200
    partial = {**CHECKS, "units": False}
    r = _post(
        client,
        bio["reviewer"],
        item["id"],
        "review",
        {"decision": "approve", "comment": "Checked the fixture", "checklist": partial},
    )
    assert r.status_code == 422 and "units" in r.json()["errors"][0]
    ok = _post(
        client,
        bio["reviewer"],
        item["id"],
        "review",
        {"decision": "approve", "comment": "Checked the fixture", "checklist": CHECKS},
    )
    assert ok.status_code == 200 and ok.json()["working"]["reviews"][-1]["checklist"] == CHECKS
    _confirm_rights(client, db, doc)
    pub = _post(client, bio["publisher"], item["id"], "publish")
    assert pub.status_code == 200, pub.text
    assert pub.json()["availability"] == "live"
    # Published questions never appear on the learner lessons endpoint: keys and explanations stay protected.
    lessons = client.get(f"/v1/chapters/{chapter.id}/lessons").json()
    assert item["id"] not in [x["id"] for x in lessons]
    assert "correct_option_id" not in str(lessons)
    queue = client.get("/v1/studio/queue?kind=mcq", headers=bio["reviewer"].headers).json()
    assert item["id"] in [q["id"] for q in queue] and all(q["kind"] == "mcq" for q in queue)


def test_quarantine_levels_and_variant_families(client: TestClient, db: Session, bio: dict[str, Staff]) -> None:
    chapter, doc = _chapter(db, 11, "biology")
    item = _new_mcq(client, bio["author"], str(chapter.id))
    _save(client, bio["author"], item, VALID, _refs(chapter, doc))
    _post(client, bio["author"], item["id"], "submit")
    _post(
        client,
        bio["reviewer"],
        item["id"],
        "review",
        {"decision": "approve", "comment": "Checked", "checklist": CHECKS},
    )
    _confirm_rights(client, db, doc)
    assert _post(client, bio["publisher"], item["id"], "publish").status_code == 200

    no_level = _post(client, bio["publisher"], item["id"], "quarantine", {"reason": "Suspected key error"})
    assert no_level.status_code == 422
    q = _post(client, bio["publisher"], item["id"], "quarantine", {"reason": "Suspected key error", "level": "SOFT"})
    assert q.status_code == 200 and q.json()["quarantine_level"] == "SOFT" and q.json()["availability"] == "quarantined"
    rel = _post(client, bio["publisher"], item["id"], "release", {"reason": "Key confirmed correct"})
    assert rel.json()["quarantine_level"] is None and rel.json()["availability"] == "live"

    variant = _new_mcq(client, bio["author"], str(chapter.id), family_of=item["id"])
    assert variant["family_id"] == item["family_id"] and variant["id"] != item["id"]
    other_chapter, _ = _chapter(db, 11, "chemistry")
    chem_author = Staff(client, db, ["content_author"], {"grades": [11], "subjects": ["chemistry"]})
    cross = client.post(
        "/v1/studio/items",
        headers=chem_author.headers,
        json={"kind": "mcq", "chapter_id": str(other_chapter.id), "title": "Cross", "family_of": item["id"]},
    )
    assert cross.status_code == 422
    lesson_family = client.post(
        "/v1/studio/items",
        headers=bio["author"].headers,
        json={"kind": "lesson", "chapter_id": str(chapter.id), "title": "Lesson", "family_of": item["id"]},
    )
    assert lesson_family.status_code == 422
    # Lessons can't take question quarantine levels.
    lesson = client.post(
        "/v1/studio/items", headers=bio["author"].headers, json={"chapter_id": str(chapter.id), "title": "Plain lesson"}
    ).json()
    assert lesson["kind"] == "lesson" and lesson["family_id"] is None and lesson["quarantine_levels"] == []
