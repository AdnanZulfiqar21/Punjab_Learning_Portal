"""W04.S1.T1 (QUESTION-TYPES-01): a written test built for short questions only, long questions only or a mix draws
from that part of the pool, and starting it reserves the weighted allowance (short 1, long 2). Technical fixture
questions in their own Class XII Chemistry chapter, so other tests' pools don't mix in."""

from __future__ import annotations

import copy
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from portal_api.db import get_sessionmaker
from portal_api.modules.access.service import QUESTION_WEIGHTS
from tests.test_written_attempts import _form, _learner


@pytest.fixture(scope="module")
def mixed_chapter(client: TestClient) -> str:
    """One published short and one published long written question, each with a reviewed rubric."""
    from tests.test_content_workflow import Staff, _chapter, _confirm_rights, _post, _refs
    from tests.test_written_records import QUESTION, R_CHECKS, W_CHECKS, _rubric

    with get_sessionmaker()() as db:
        scope = {"grades": [12], "subjects": ["chemistry"]}
        author = Staff(client, db, ["content_author"], scope)
        reviewer = Staff(client, db, ["subject_reviewer"], scope)
        publisher = Staff(client, db, ["publisher"], scope, mfa=True)
        chapter, doc = _chapter(db, 12, "chemistry", 4)
        _confirm_rights(client, db, doc)
        for question_type in ("short", "long"):
            body = copy.deepcopy(QUESTION)
            body["question_type"] = question_type
            q = client.post(
                "/v1/studio/items",
                headers=author.headers,
                json={"kind": "written", "chapter_id": str(chapter.id), "title": f"Fixture {question_type}"},
            ).json()
            saved = client.put(
                f"/v1/studio/items/{q['id']}/draft",
                headers=author.headers,
                json={"revision": q["working"]["revision"], "body": body, "source_refs": _refs(chapter, doc)},
            )
            assert saved.status_code == 200, saved.text
            assert _post(client, author, q["id"], "submit").status_code == 200
            q = _post(
                client,
                reviewer,
                q["id"],
                "review",
                {"decision": "approve", "comment": "Fixture check", "checklist": W_CHECKS},
            ).json()
            r = client.post(
                "/v1/studio/items",
                headers=author.headers,
                json={"kind": "rubric", "parent_item_id": q["id"], "title": "Rubric"},
            ).json()
            client.put(
                f"/v1/studio/items/{r['id']}/draft",
                headers=author.headers,
                json={
                    "revision": r["working"]["revision"],
                    "body": _rubric(q["working"]["id"]),
                    "source_refs": _refs(chapter, doc),
                },
            )
            assert _post(client, author, r["id"], "submit").status_code == 200
            rv = _post(
                client,
                reviewer,
                r["id"],
                "review",
                {"decision": "approve", "comment": "Fixture check", "checklist": R_CHECKS},
            )
            assert rv.status_code == 200, rv.text
            assert _post(client, publisher, r["id"], "publish").status_code == 200
            assert _post(client, publisher, q["id"], "publish").status_code == 200
        from portal_api.modules.written.review import ReviewCapacity

        if db.get(ReviewCapacity, (12, "chemistry")) is None:
            db.add(ReviewCapacity(grade_number=12, subject_code="chemistry", max_open_cases=10_000, reason="fixture"))
            db.commit()
        return str(chapter.id)


def _types(form_id: str) -> list[str]:
    with get_sessionmaker()() as db:
        rows = db.execute(
            text(
                "select v.body->>'question_type' from written_form_item i "
                "join content_version v on v.id = i.question_version_id where i.form_id = :f order by i.position"
            ),
            {"f": form_id},
        ).scalars()
        return list(rows)


def _available(client: TestClient, who: Any) -> int:
    return int(client.get("/v1/me/access", headers=who.headers).json()["written_allowance"]["available"])


@pytest.mark.parametrize(("question_type", "expected"), [("short", ["short"]), ("long", ["long"])])
def test_a_one_type_build_draws_only_that_type_and_reserves_its_weight(
    client: TestClient, mixed_chapter: str, question_type: str, expected: list[str]
) -> None:
    who = _learner(client)
    form = _form(client, who, mixed_chapter, question_count=1, question_type=question_type)
    assert form.status_code == 201, form.text
    assert _types(form.json()["id"]) == expected
    before = _available(client, who)
    started = client.post(f"/v1/written/forms/{form.json()['id']}/attempt", headers=who.headers)
    assert started.status_code == 200, started.text
    assert before - _available(client, who) == QUESTION_WEIGHTS[question_type]


def test_a_mixed_build_takes_both_types_and_their_summed_weight(client: TestClient, mixed_chapter: str) -> None:
    who = _learner(client)
    form = _form(client, who, mixed_chapter, question_count=2, question_type="mixed")
    assert form.status_code == 201, form.text
    assert sorted(_types(form.json()["id"])) == ["long", "short"]
    before = _available(client, who)
    assert client.post(f"/v1/written/forms/{form.json()['id']}/attempt", headers=who.headers).status_code == 200
    assert before - _available(client, who) == QUESTION_WEIGHTS["short"] + QUESTION_WEIGHTS["long"]


def test_a_one_type_build_never_tops_up_from_the_other_type(client: TestClient, mixed_chapter: str) -> None:
    who = _learner(client)
    refused = _form(client, who, mixed_chapter, question_count=2, question_type="long")
    assert refused.status_code == 422, refused.text
    assert (refused.json()["available"], refused.json()["requested"]) == (1, 2)
    assert (
        client.post(
            "/v1/written/forms",
            headers={**who.headers, "Idempotency-Key": uuid.uuid4().hex},
            json={"grade": 12, "subject": "chemistry", "chapter_ids": [mixed_chapter], "question_count": 2},
        ).status_code
        == 201
    )  # the default (mixed) has two
