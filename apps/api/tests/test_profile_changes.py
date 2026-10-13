"""P05.S4.T3 (PROFILE-CHANGES-01): profile changes reach new mocks only.

* A newly published version shapes new mocks. An attempt already built keeps the version it pinned: its deadline,
  marks, negative marking and invalid-item policy.
* A reviewed correction stays a separate record. Each form applies its own pinned policy, a finished attempt gets a
  new score version (the first one is kept), and no deadline moves.
* Unknown years, missing sources, conflicting book editions, an older year replacing a newer one and unknown patterns
  are refused with errors that say what to fix.

Profiles, questions, corrections and the second book edition are labelled technical fixtures, not official patterns
or academic content. The extra edition exists only inside this test and is removed afterwards.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text, update
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from portal_api.modules.assessment import profiles
from portal_api.modules.curriculum.models import BookEdition, Chapter, Grade, SourceDocument, Subject
from tests.test_attempts import _form_item_ids, _learner, _op, _save_ops, _start
from tests.test_content_workflow import Staff, _post
from tests.test_mcq_corrections import _adjudicator, _correct, _keys, _result
from tests.test_mocks import _mock, _publish_profile

PHYSICS_XI = [{"subject": "physics", "grades": [11], "questions": 3}]
RULES: dict[str, Any] = {
    "source_url": "https://example.invalid/fixture",
    "source_note": "Fixture: technical pattern for tests.",
    "duration_minutes": 30,
    "question_pool": "any",
    "sections": PHYSICS_XI,
}


def _staff(client: TestClient) -> tuple[Staff, Staff, Staff]:
    with get_sessionmaker()() as db:
        return (
            Staff(client, db, ["academic_adjudicator"], mfa=True),
            Staff(client, db, ["academic_adjudicator"], mfa=True),
            Staff(client, db, ["owner_admin"], mfa=True),
        )


def _draft(client: TestClient, code: str, year: int, rules: dict[str, Any]) -> tuple[Any, Staff, Staff]:
    """A new draft version of an existing profile by a new author, with two other people free to verify it."""
    author, first, second = _staff(client)
    pid = next(
        p["id"] for p in client.get("/v1/admin/exam-profiles", headers=first.headers).json() if p["code"] == code
    )
    made = client.post(
        f"/v1/admin/exam-profiles/{pid}/versions", headers=author.headers, json={"year": year, "rules": rules}
    )
    return made, first, second


def _verified(client: TestClient, code: str, year: int, rules: dict[str, Any]) -> tuple[str, Staff]:
    made, first, second = _draft(client, code, year, rules)
    assert made.status_code == 201, made.text
    vid = made.json()["id"]
    for who in (first, second):
        ok = client.post(
            f"/v1/admin/exam-profile-versions/{vid}/verify", headers=who.headers, json={"note": "Fixture verification"}
        )
        assert ok.status_code == 200, ok.text
    return vid, first


def _publish(client: TestClient, vid: str, who: Staff) -> Any:
    return client.post(f"/v1/admin/exam-profile-versions/{vid}/publish", headers=who.headers)


def _answer_and_submit(client: TestClient, who: Staff, attempt_id: str, form_id: str, wrong: int) -> None:
    """Answer every question with its published key, except one deliberately wrong answer, and submit."""
    keys = _keys(form_id)
    ops = [
        _op(p, 1, keys[p] if p != wrong else next(o for o in ("o1", "o2", "o3", "o4") if o != keys[p]))
        for p in sorted(keys)
    ]
    assert _save_ops(client, who, attempt_id, *ops).status_code == 200
    done = client.post(
        f"/v1/attempts/{attempt_id}/submit", headers=who.headers, json={"idempotency_key": uuid.uuid4().hex, "ops": []}
    )
    assert done.status_code == 200, done.text


def _frozen(form_id: str) -> tuple[str, list[tuple[int, str, int]]]:
    """A form's pinned invalid-item policy and its frozen (position, question version, marks)."""
    with get_sessionmaker()() as db:
        policy = db.execute(
            text("select invalid_item_treatment from practice_form where id = :f"), {"f": form_id}
        ).scalar_one()
        rows = db.execute(
            text("select position, version_id, marks from form_item where form_id = :f order by position"),
            {"f": form_id},
        ).all()
        return str(policy), [(int(p), str(v), int(m)) for p, v, m in rows]


def _without_clash(make: Any, first_form_id: str) -> dict[str, Any]:
    """Both mocks draw at random from one pool, so a question can appear in both. Redraw the second until the
    questions each check relies on are distinct: question 1 of each mock is voided below, and question 2 of each is
    answered wrong (a voided question elsewhere in the other mock would change its expected marks)."""
    first = _form_item_ids(first_form_id)
    for _ in range(10):
        form = make()
        second = _form_item_ids(form["id"])
        if second[1] not in (first[2], first[3]) and first[1] != second[2]:
            return dict(form)
    raise AssertionError("couldn't draw a second mock without a clashing question")


def test_a_new_version_reaches_new_mocks_and_corrections_keep_each_pinned_policy(
    client: TestClient, db: Session, physics: dict[str, Any]
) -> None:
    # v1: 30 minutes, 2 marks a question, 1 off for a wrong answer, a void question is excluded.
    code = _publish_profile(client, db, PHYSICS_XI)
    learner, other = _learner(client), _learner(client)
    first_form = _mock(client, learner, code).json()
    first = _start(client, learner, first_form["id"])
    first_frozen = _frozen(first_form["id"])
    assert first_frozen[0] == "EXCLUDE" and all(m == 2 for _, _, m in first_frozen[1])

    # v2 (a corrected pattern for the next year): 45 minutes, 3 marks, no negative marking, a void question credits all.
    v2_rules = {
        **RULES,
        "duration_minutes": 45,
        "marks_per_question": 3,
        "negative_marks": 0,
        "invalid_item_treatment": "CREDIT_ALL",
    }
    vid, publisher = _verified(client, code, 2027, v2_rules)
    assert _publish(client, vid, publisher).json()["status"] == "published"

    # The attempt already started keeps v1: same deadline, same marks; its frozen form is unchanged.
    resumed = client.get(f"/v1/attempts/{first['id']}", headers=learner.headers).json()
    assert resumed["deadline_at"] == first["deadline_at"] and [i["marks"] for i in resumed["items"]] == [2, 2, 2]
    assert _frozen(first_form["id"]) == first_frozen

    # A new mock follows v2 (another learner's: a learner has one mock open at a time, EXAM-ROOM-01).
    second_form = _without_clash(lambda: _mock(client, other, code).json(), first_form["id"])
    assert (first_form["scope"]["profile_version"], second_form["scope"]["profile_version"]) == (1, 2)
    assert (first_form["scope"]["year"], second_form["scope"]["year"]) == (2026, 2027)
    assert (first_form["duration_s"], second_form["duration_s"]) == (1800, 2700)
    assert (first_form["negative_marks"], second_form["negative_marks"]) == (1, 0)
    second = _start(client, other, second_form["id"])
    assert [i["marks"] for i in second["items"]] == [3, 3, 3] and _frozen(second_form["id"])[0] == "CREDIT_ALL"

    # The first mock is submitted under v1: question 2 is wrong (-1), the others earn 2 each.
    _answer_and_submit(client, learner, first["id"], first_form["id"], wrong=2)
    scored = _result(client, learner, first["id"])
    assert (scored["raw"], scored["maximum"], scored["version"]) == (3, 6, 1)

    # A reviewed VOID correction lands on question 1 of each mock.
    voided = {_form_item_ids(first_form["id"])[1], _form_item_ids(second_form["id"])[1]}
    pub, adjudicator = physics["publisher"], _adjudicator(client)
    try:
        for item in voided:
            quarantined = _post(client, pub, item, "quarantine", {"reason": "Fixture: void", "level": "VOID"})
            assert quarantined.status_code == 200, quarantined.text
            made = _correct(client, adjudicator, item, defect="VOID", reason="Fixture: no valid option")
            assert made.status_code == 201, made.text

        # The finished mock is re-scored with its own pinned policy (EXCLUDE) as a new version; the first is kept.
        revised = _result(client, learner, first["id"])
        assert (revised["raw"], revised["maximum"], revised["version"]) == (1, 4, 2) and revised["revision_reason"]
        assert revised["items"][0]["treatment"] == "EXCLUDE"
        with get_sessionmaker()() as s:
            history = s.execute(
                text("select version, raw, maximum from score_version where attempt_id = :a order by version"),
                {"a": first["id"]},
            ).all()
        assert [tuple(h) for h in history] == [(1, 3, 6), (2, 1, 4)]

        # The open mock keeps its deadline and gets the correction at submission, with its own policy (CREDIT_ALL).
        still = client.get(f"/v1/attempts/{second['id']}", headers=other.headers).json()
        assert still["deadline_at"] == second["deadline_at"]
        _answer_and_submit(client, other, second["id"], second_form["id"], wrong=2)
        credited = _result(client, other, second["id"])
        assert (credited["raw"], credited["maximum"], credited["version"]) == (6, 9, 1)
        assert credited["items"][0]["treatment"] == "CREDIT_ALL"

        # Corrections are separate reviewed records: the frozen forms and the first deadline are untouched.
        assert _frozen(first_form["id"]) == first_frozen
        assert (
            client.get(f"/v1/attempts/{first['id']}", headers=learner.headers).json()["deadline_at"]
            == first["deadline_at"]
        )
        for item in voided:
            records = client.get(f"/v1/studio/items/{item}/score-corrections", headers=adjudicator.headers).json()
            assert any(r["defect"] == "VOID" and r["status"] == "effective" for r in records)
    finally:
        with get_sessionmaker()() as s:
            for item in voided:
                s.execute(text("update mcq_adjudication set status = 'superseded' where item_id = :i"), {"i": item})
            s.commit()
        for item in voided:
            _post(client, pub, item, "release", {"reason": "Fixture cleanup"})


def test_unknown_years_missing_sources_and_older_versions_are_refused_clearly(
    client: TestClient, db: Session, physics: dict[str, Any]
) -> None:
    code = _publish_profile(client, db, PHYSICS_XI)

    unknown_year, *_ = _draft(client, code, 1999, RULES)
    assert unknown_year.status_code == 422
    assert unknown_year.json()["errors"] == [
        {"loc": ["body", "year"], "msg": "Input should be greater than or equal to 2020"}
    ]

    no_source = {k: v for k, v in RULES.items() if k != "source_url"}
    missing, *_ = _draft(client, code, 2026, no_source)
    assert missing.status_code == 422 and any(e.startswith("source_url:") for e in missing.json()["errors"])

    unsupported, *_ = _draft(client, code, 2026, {**RULES, "sections": [{**PHYSICS_XI[0], "grades": [13]}]})
    assert unsupported.status_code == 422 and any("grades" in e for e in unsupported.json()["errors"])

    # A version for an older exam year can't replace the published 2026 version.
    vid, publisher = _verified(client, code, 2025, RULES)
    older = _publish(client, vid, publisher)
    assert older.status_code == 409 and "older than the published version 1 for 2026" in older.json()["detail"]

    # An unknown pattern says so.
    learner = _learner(client)
    for r in (
        _mock(client, learner, "NO-SUCH-PATTERN"),
        client.get("/v1/mocks/NO-SUCH/readiness", headers=learner.headers),
    ):
        assert r.status_code == 404 and r.json()["detail"] == "No published test pattern with that code."


def _second_edition(subject: str, grade: int) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Commit a labelled technical second edition (source, book, one live chapter) of a class and subject."""
    tag = uuid.uuid4().hex[:8]
    with get_sessionmaker()() as s:
        subject_id = s.scalar(select(Subject.id).where(Subject.code == subject))
        grade_id = s.scalar(select(Grade.id).where(Grade.number == grade))
        source = SourceDocument(
            id=uuid.uuid4(),
            source_id=f"FIXTURE-ED-{tag}",
            grade_number=grade,
            subject_code=subject,
            title="Fixture: technical second edition",
            edition="Fixture edition",
            file_path="fixture/none.pdf",
            sha256="0" * 64,
            bytes=0,
            pdf_pages=0,
            completeness="complete",
            rights="Fixture: technical record only",
            status="fixture",
        )
        book = BookEdition(
            id=uuid.uuid4(),
            natural_key=f"fixture-edition-{tag}",
            grade_id=grade_id,
            subject_id=subject_id,
            source_document_id=source.id,
            title="Fixture: technical second edition",
            chapter_label="Chapter",
        )
        chapter = Chapter(
            id=uuid.uuid4(),
            natural_key=f"fixture-edition-{tag}-ch1",
            book_id=book.id,
            display_order=1,
            number=1,
            title="Fixture chapter",
            status="complete",
        )
        s.add(source)
        s.flush()
        s.add(book)
        s.flush()
        s.add(chapter)
        s.commit()
        return source.id, book.id, chapter.id


def test_conflicting_or_missing_book_editions_are_named(
    client: TestClient, db: Session, physics: dict[str, Any]
) -> None:
    code = _publish_profile(client, db, PHYSICS_XI)
    learner = _learner(client)
    assert client.get(f"/v1/mocks/{code}/readiness", headers=learner.headers).json()["problems"] == []
    vid, publisher = _verified(client, code, 2026, RULES)  # checked before the catalogue changed

    source_id, book_id, chapter_id = _second_edition("physics", 11)
    try:
        conflict = "Section 1: the catalogue has 2 Class XI Physics book editions ("
        ready = client.get(f"/v1/mocks/{code}/readiness", headers=learner.headers).json()
        assert ready["ready"] is False and ready["problems"][0].startswith(conflict)
        assert "Fixture: technical second edition" in ready["problems"][0]
        built = _mock(client, learner, code)
        assert built.status_code == 409 and built.json()["code_reason"] == "PATTERN_UNSUPPORTED"
        assert built.json()["problems"] == ready["problems"]
        published = _publish(client, vid, publisher)
        assert published.status_code == 409 and published.json()["errors"][0].startswith(conflict)
        draft, *_ = _draft(client, code, 2026, RULES)
        assert draft.status_code == 422 and draft.json()["errors"][0].startswith(conflict)
    finally:
        with get_sessionmaker()() as s:
            s.execute(delete(Chapter).where(Chapter.id == chapter_id))
            s.execute(delete(BookEdition).where(BookEdition.id == book_id))
            s.execute(delete(SourceDocument).where(SourceDocument.id == source_id))
            s.commit()
    assert client.get(f"/v1/mocks/{code}/readiness", headers=learner.headers).json()["problems"] == []

    # With no live book for a class, a section has nothing to draw from (checked without committing anything).
    with get_sessionmaker()() as s:
        s.execute(
            update(Chapter)
            .where(
                Chapter.book_id.in_(
                    select(BookEdition.id)
                    .join(Grade, Grade.id == BookEdition.grade_id)
                    .join(Subject, Subject.id == BookEdition.subject_id)
                    .where(Grade.number == 12, Subject.code == "physics")
                )
            )
            .values(retired_at=text("now()"))
        )
        problems = profiles.catalogue_problems(s, [{"subject": "physics", "grades": [11, 12], "questions": 3}])
        s.rollback()
    assert problems == [
        "Section 1: the catalogue has no Class XII Physics book, so this section has nothing to draw from."
    ]
