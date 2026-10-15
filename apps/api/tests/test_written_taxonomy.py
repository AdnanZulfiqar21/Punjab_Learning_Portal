"""W01.S1.T1 (TAXONOMY-01): numerical and derivation written questions are modelled with what each needs (an expected
equation; a numerical answer's unit) and guides that state the matching rules (units and significant figures; carried
-forward errors). They can be reviewed and published, but learners are offered short and long questions only until
each new slice is qualified (WA-D11). Technical fixture questions in their own Class XII Chemistry chapter."""

from __future__ import annotations

import copy
import uuid
from typing import Any

from fastapi.testclient import TestClient

from portal_api.db import get_sessionmaker
from portal_api.modules.content import written as wq
from tests.test_written_attempts import _form, _learner
from tests.test_written_records import QUESTION, R_CHECKS, W_CHECKS, _rubric

NUMERICAL = {**copy.deepcopy(QUESTION), "question_type": "numerical", "expected_structures": ["equation"]}


def _errors(body: dict[str, Any]) -> list[str]:
    return list(wq.validate_written(body, for_publication=False).errors)


def test_each_type_states_what_it_needs() -> None:
    assert any("tick Equation" in e for e in _errors({**NUMERICAL, "expected_structures": []}))
    assert any("unit of the final answer" in e for e in _errors(NUMERICAL))
    assert _errors({**NUMERICAL, "answer_unit": "mol"}) == []
    assert any("Only a numerical question" in e for e in _errors({**QUESTION, "answer_unit": "mol"}))
    derivation = {**copy.deepcopy(QUESTION), "question_type": "derivation"}
    assert any("tick Equation" in e for e in _errors(derivation))
    assert _errors({**derivation, "expected_structures": ["equation"]}) == []
    assert _errors(QUESTION) == []  # short and long questions are unchanged


def test_a_guide_states_the_rules_its_question_type_needs() -> None:
    def reconcile(question: dict[str, Any], **rules: str) -> list[str]:
        q, _ = wq.parse_written(question)
        r, _ = wq.parse_rubric({**_rubric(str(uuid.uuid4())), **rules})
        assert q is not None and r is not None
        return wq.reconcile(r, q)

    numerical = {**NUMERICAL, "answer_unit": "mol"}
    missing = reconcile(numerical)
    assert any("units rule" in e for e in missing) and any("significant-figures rule" in e for e in missing)
    assert reconcile(numerical, units_rule="Fixture: unit required", significant_figures_rule="Fixture: 3 s.f.") == []
    derivation = {**copy.deepcopy(QUESTION), "question_type": "derivation", "expected_structures": ["equation"]}
    assert any("carried-forward error" in e for e in reconcile(derivation))
    assert reconcile(derivation, consequential_error_rule="Fixture: follow through once") == []
    assert reconcile(QUESTION) == []


def test_a_published_numerical_question_is_not_offered_to_learners(client: TestClient) -> None:
    from tests.test_content_workflow import Staff, _chapter, _confirm_rights, _post, _refs

    with get_sessionmaker()() as db:
        scope = {"grades": [12], "subjects": ["chemistry"]}
        author = Staff(client, db, ["content_author"], scope)
        reviewer = Staff(client, db, ["subject_reviewer"], scope)
        publisher = Staff(client, db, ["publisher"], scope, mfa=True)
        # Index 5 is Hydroxy Compounds, where test_w06_review.py publishes a short fixture. Index 7
        # (Organic Nitrogen) is the Class XII Chemistry chapter no other written fixture uses.
        chapter, doc = _chapter(db, 12, "chemistry", 7)
        _confirm_rights(client, db, doc)
    q = client.post(
        "/v1/studio/items",
        headers=author.headers,
        json={"kind": "written", "chapter_id": str(chapter.id), "title": "Fixture numerical"},
    ).json()
    body = {**NUMERICAL, "answer_unit": "mol"}
    saved = client.put(
        f"/v1/studio/items/{q['id']}/draft",
        headers=author.headers,
        json={"revision": q["working"]["revision"], "body": body, "source_refs": _refs(chapter, doc)},
    )
    assert saved.status_code == 200, saved.text
    assert _post(client, author, q["id"], "submit").status_code == 200
    review = {"decision": "approve", "comment": "Fixture check", "checklist": W_CHECKS}
    q = _post(client, reviewer, q["id"], "review", review).json()
    r = client.post(
        "/v1/studio/items",
        headers=author.headers,
        json={"kind": "rubric", "parent_item_id": q["id"], "title": "Rubric"},
    ).json()
    guide = {
        **_rubric(q["working"]["id"]),
        "units_rule": "Fixture: the unit is required",
        "significant_figures_rule": "Fixture: three significant figures",
    }
    saved = client.put(
        f"/v1/studio/items/{r['id']}/draft",
        headers=author.headers,
        json={"revision": r["working"]["revision"], "body": guide, "source_refs": _refs(chapter, doc)},
    )
    assert saved.status_code == 200, saved.text
    assert _post(client, author, r["id"], "submit").status_code == 200
    rubric_review = {"decision": "approve", "comment": "Fixture check", "checklist": R_CHECKS}
    assert _post(client, reviewer, r["id"], "review", rubric_review).status_code == 200
    assert _post(client, publisher, r["id"], "publish").status_code == 200
    assert _post(client, publisher, q["id"], "publish").status_code == 200  # reviewed and published

    learner = _learner(client)
    shown = client.get(
        "/v1/written/availability", headers=learner.headers, params={"grade": 12, "subject": "chemistry"}
    ).json()
    [row] = [c for c in shown["chapters"] if c["chapter_id"] == str(chapter.id)]
    from sqlalchemy import select

    from portal_api.modules.content.models import ContentItem, ContentVersion

    with get_sessionmaker()() as db:
        stored = db.execute(
            select(ContentVersion.body)
            .join(ContentItem, ContentItem.published_version_id == ContentVersion.id)
            .where(ContentItem.id == uuid.UUID(q["id"]))
        ).scalar_one()
    assert stored["question_type"] == "numerical"  # published as a numerical question, not rewritten to short
    assert row["questions"] == 0  # not offered: the numerical slice isn't qualified (WA-D11)
    built = _form(client, learner, str(chapter.id))
    assert built.status_code == 422, built.text
