"""Written questions and rubrics (§20.6): integer-hundredth marks, subpart reconciliation, rubric authority, the
question↔rubric publication order and key isolation. Text is a technical fixture, not academic content."""

from __future__ import annotations

import copy
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.test_content_workflow import Staff, _chapter, _confirm_rights, _post, _refs

W_CHECKS = {c: True for c in ("accuracy", "ambiguity", "mapping", "marks", "structures")}
R_CHECKS = {
    c: True for c in ("authority", "reconciliation", "alternative_routes", "consequential_errors", "units_and_wording")
}


def _p(text: str) -> list[dict[str, Any]]:
    return [{"type": "paragraph", "text": text}]


QUESTION: dict[str, Any] = {
    "question_type": "short",
    "stem": _p("Fixture written question stem."),
    "subparts": [
        {"id": "a", "label": "(a)", "blocks": _p("Fixture part a"), "max_units": 200},
        {"id": "b", "label": "(b)", "blocks": _p("Fixture part b"), "max_units": 300},
    ],
    "max_units": 500,
}


def _rubric(question_version_id: str) -> dict[str, Any]:
    return {
        "question_version_id": question_version_id,
        "authority": "practice_rubric",
        "increment_units": 50,
        "criteria": [
            {
                "id": "a1",
                "subpart_id": "a",
                "description": "Fixture criterion a1",
                "max_units": 200,
                "levels": [0, 100, 200],
            },
            {
                "id": "b1",
                "subpart_id": "b",
                "description": "Fixture method one",
                "max_units": 300,
                "levels": [0, 150, 300],
                "alternative_group": "route",
            },
            {
                "id": "b2",
                "subpart_id": "b",
                "description": "Fixture method two",
                "max_units": 300,
                "levels": [0, 300],
                "alternative_group": "route",
            },
        ],
        "expected_concepts": ["Fixture concept"],
    }


@pytest.fixture
def chem(client: TestClient, db: Session) -> dict[str, Staff]:
    scope = {"grades": [12], "subjects": ["chemistry"]}
    return {
        "author": Staff(client, db, ["content_author"], scope),
        "reviewer": Staff(client, db, ["subject_reviewer"], scope),
        "publisher": Staff(client, db, ["publisher"], scope, mfa=True),
    }


def _create(client: TestClient, who: Staff, **body: Any) -> Any:
    return client.post("/v1/studio/items", headers=who.headers, json={"title": "Fixture", **body})


def _save(client: TestClient, who: Staff, item: dict[str, Any], body: dict[str, Any], refs: list[Any]) -> Any:
    return client.put(
        f"/v1/studio/items/{item['id']}/draft",
        headers=who.headers,
        json={"revision": item["working"]["revision"], "body": body, "source_refs": refs},
    )


def _approved_question(client: TestClient, db: Session, chem: dict[str, Staff]) -> tuple[dict[str, Any], Any, Any]:
    chapter, doc = _chapter(db, 12, "chemistry")
    q = _create(client, chem["author"], kind="written", chapter_id=str(chapter.id)).json()
    assert _save(client, chem["author"], q, QUESTION, _refs(chapter, doc)).status_code == 200
    assert _post(client, chem["author"], q["id"], "submit").status_code == 200
    ok = _post(
        client,
        chem["reviewer"],
        q["id"],
        "review",
        {"decision": "approve", "comment": "Fixture check", "checklist": W_CHECKS},
    )
    assert ok.status_code == 200, ok.text
    return ok.json(), chapter, doc


def test_written_question_rules(client: TestClient, db: Session, chem: dict[str, Staff]) -> None:
    chapter, doc = _chapter(db, 12, "chemistry")
    q = _create(client, chem["author"], kind="written", chapter_id=str(chapter.id)).json()
    assert q["kind"] == "written" and q["family_id"] == q["id"] and q["review_checklist"] == list(W_CHECKS)
    bad = copy.deepcopy(QUESTION)
    bad["max_units"] = 400  # subparts add up to 500
    assert _save(client, chem["author"], q, bad, _refs(chapter, doc)).status_code == 200  # drafts may be inconsistent
    r = _post(client, chem["author"], q["id"], "submit")
    assert r.status_code == 422 and any("add up to the question maximum" in e for e in r.json()["errors"])


def test_rubrics_attach_to_written_questions_only(client: TestClient, db: Session, chem: dict[str, Staff]) -> None:
    chapter, _ = _chapter(db, 12, "chemistry")
    lesson = _create(client, chem["author"], chapter_id=str(chapter.id)).json()
    assert _create(client, chem["author"], kind="rubric", chapter_id=str(chapter.id)).status_code == 422
    on_lesson = _create(client, chem["author"], kind="rubric", chapter_id=str(chapter.id), parent_item_id=lesson["id"])
    assert on_lesson.status_code == 422
    q = _create(client, chem["author"], kind="written", chapter_id=str(chapter.id)).json()
    rubric = _create(client, chem["author"], kind="rubric", chapter_id=str(chapter.id), parent_item_id=q["id"]).json()
    assert rubric["parent_item_id"] == q["id"] and rubric["chapter_id"] == q["chapter_id"]
    assert rubric["review_checklist"] == list(R_CHECKS)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda r: r["criteria"][0].update(levels=[100, 200]), "include 0 and its maximum"),
        (lambda r: r["criteria"][0].update(levels=[0, 75, 200]), "multiple of the increment"),
        (
            lambda r: r["criteria"][0].update(max_units=150, levels=[0, 150]),
            "add up to 150 units but its maximum is 200",
        ),
        (lambda r: r["criteria"][1].update(alternative_group=None), "add up to 600 units but its maximum is 300"),
        (lambda r: r["criteria"][0].update(subpart_id="z"), "doesn't have as a slot"),
        (lambda r: r.update(authority="official_scheme"), "official marking scheme needs a reference"),
        (lambda r: r["criteria"][0].update(depends_on=["nope"]), "depends on unknown"),
    ],
)
def test_rubric_rules_and_reconciliation(
    client: TestClient, db: Session, chem: dict[str, Staff], mutate: Any, message: str
) -> None:
    q, chapter, doc = _approved_question(client, db, chem)
    rubric = _create(client, chem["author"], kind="rubric", chapter_id=str(chapter.id), parent_item_id=q["id"]).json()
    body = _rubric(q["working"]["id"])
    mutate(body)
    assert _save(client, chem["author"], rubric, body, _refs(chapter, doc)).status_code == 200
    r = _post(client, chem["author"], rubric["id"], "submit")
    assert r.status_code == 422 and any(message in e for e in r.json()["errors"]), r.json()


def test_publication_order_and_key_isolation(client: TestClient, db: Session, chem: dict[str, Staff]) -> None:
    q, chapter, doc = _approved_question(client, db, chem)
    _confirm_rights(client, db, doc)
    # The question can't go live without a published rubric for this exact version.
    early = _post(client, chem["publisher"], q["id"], "publish")
    assert early.status_code == 422 and any("rubric" in e for e in early.json()["errors"])

    rubric = _create(client, chem["author"], kind="rubric", chapter_id=str(chapter.id), parent_item_id=q["id"]).json()
    assert _save(client, chem["author"], rubric, _rubric(q["working"]["id"]), _refs(chapter, doc)).status_code == 200
    assert _post(client, chem["author"], rubric["id"], "submit").status_code == 200
    approved = _post(
        client,
        chem["reviewer"],
        rubric["id"],
        "review",
        {"decision": "approve", "comment": "Fixture rubric check", "checklist": R_CHECKS},
    )
    assert approved.status_code == 200, approved.text
    assert _post(client, chem["publisher"], rubric["id"], "publish").status_code == 200
    live = _post(client, chem["publisher"], q["id"], "publish")
    assert live.status_code == 200 and live.json()["availability"] == "live"
    # Neither the question nor the rubric is ever served by learner content APIs.
    lessons = client.get(f"/v1/chapters/{chapter.id}/lessons").json()
    assert {q["id"], rubric["id"]}.isdisjoint({x["id"] for x in lessons})


def test_rubric_needs_an_approved_question_version_to_publish(
    client: TestClient, db: Session, chem: dict[str, Staff]
) -> None:
    chapter, doc = _chapter(db, 12, "chemistry")
    _confirm_rights(client, db, doc)
    q = _create(client, chem["author"], kind="written", chapter_id=str(chapter.id)).json()
    _save(client, chem["author"], q, QUESTION, _refs(chapter, doc))
    assert _post(client, chem["author"], q["id"], "submit").status_code == 200  # submitted, not approved
    rubric = _create(client, chem["author"], kind="rubric", chapter_id=str(chapter.id), parent_item_id=q["id"]).json()
    _save(client, chem["author"], rubric, _rubric(q["working"]["id"]), _refs(chapter, doc))
    assert _post(client, chem["author"], rubric["id"], "submit").status_code == 200
    _post(
        client,
        chem["reviewer"],
        rubric["id"],
        "review",
        {"decision": "approve", "comment": "Fixture rubric check", "checklist": R_CHECKS},
    )
    r = _post(client, chem["publisher"], rubric["id"], "publish")
    assert r.status_code == 422 and any("must be academically approved" in e for e in r.json()["errors"])
    # A rubric can't mark another question's version.
    other, _, _ = _approved_question(client, db, chem)
    stray = _create(client, chem["author"], kind="rubric", chapter_id=str(chapter.id), parent_item_id=q["id"]).json()
    _save(client, chem["author"], stray, _rubric(other["working"]["id"]), _refs(chapter, doc))
    s = _post(client, chem["author"], stray["id"], "submit")
    assert s.status_code == 422 and any("its own question" in e for e in s.json()["errors"])
