"""Development/test-only fixture for the rubric-correction browser journey (W06.S2.T3; PR #34 review W06-10).

    portal-dev-fixture-rubric-correction setup            # prints JSON: chapter, question and rubric ids
    portal-dev-fixture-rubric-correction correct RUBRIC_ID --kind scoring|notes   # publishes a corrected version

In development and CI, publication rights stay unverified, so a corrected rubric can't be published through the
editorial workflow there. This command stands in for that step only, in an isolated Class XI Biology chapter (the
second one), so the rest of the journey (an MFA adjudicator approving and applying the correction, the worker, the
teacher's regrade and the learner's result) runs through the real UI and API. ``setup`` retires earlier copies of the
fixture so a test always gets exactly one question. Every write is audited as a technical fixture. The text says it is
a technical fixture and is not academic content.

Refused unless the role is development/test and the development identity adapter is enabled (the same guard as
``portal-dev-seed-practice``).
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import uuid
from typing import Any

from sqlalchemy import select

from portal_api.config import get_settings
from portal_api.db import get_sessionmaker
from portal_api.modules.audit.models import record
from portal_api.modules.content import blocks
from portal_api.modules.content.dev_fixtures import FIXTURE_PREFIX, _p
from portal_api.modules.content.models import ContentItem, ContentVersion
from portal_api.modules.curriculum.models import BookEdition, Chapter, Grade, Subject
from portal_api.modules.identity.models import AppUser

TITLE = "Rubric-correction journey"


def _rubric(question_version_id: uuid.UUID) -> dict[str, Any]:
    return {
        "question_version_id": str(question_version_id),
        "authority": "practice_rubric",
        "increment_units": 50,
        "criteria": [
            {
                "id": "a1",
                "subpart_id": "a",
                "description": "Fixture criterion for part a",
                "max_units": 200,
                "levels": [0, 100, 200],
                "depends_on": [],
            },
            {
                "id": "b1",
                "subpart_id": "b",
                "description": "Fixture criterion for part b",
                "max_units": 300,
                "levels": [0, 150, 300],
                "depends_on": [],
            },
        ],
        "expected_concepts": ["Fixture concept"],
        "alternative_routes": [],
    }


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    if settings.role not in ("development", "test") or not settings.dev_auth_enabled:
        print("refusing: this fixture exists only for development/test with the dev identity adapter", file=sys.stderr)
        return 2
    p = argparse.ArgumentParser(prog="portal-dev-fixture-rubric-correction")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup")
    c = sub.add_parser("correct")
    c.add_argument("rubric_id")
    c.add_argument("--kind", choices=("scoring", "notes"), default="scoring")
    args = p.parse_args(argv)
    with get_sessionmaker()() as db:
        author = db.scalar(select(AppUser).where(AppUser.email == "studio-author@example.com"))
        if author is None:
            print("run portal-dev-seed-staff first", file=sys.stderr)
            return 1
        if args.cmd == "setup":
            out = _setup(db, author.id)
        else:
            out = _correct(db, author.id, uuid.UUID(args.rubric_id), args.kind)
        db.commit()
    print(json.dumps(out))
    return 0


def _version(item_id: uuid.UUID, number: int, body: dict[str, Any], author: uuid.UUID, kind: str) -> ContentVersion:
    return ContentVersion(
        id=uuid.uuid4(),
        item_id=item_id,
        number=number,
        status="published",
        revision=1,
        content_schema_version=blocks.CONTENT_SCHEMA_VERSION,
        body=body,
        block_types=["paragraph"] if kind != "rubric" else [],
        source_refs=[],
        change_reason=None if number == 1 else "technical fixture correction",
        created_by=author,
        contributors=[str(author)],
        updated_by=author,
    )


def _setup(db: Any, author: uuid.UUID) -> dict[str, Any]:
    chapter = db.scalars(
        select(Chapter)
        .join(BookEdition, BookEdition.id == Chapter.book_id)
        .join(Grade, Grade.id == BookEdition.grade_id)
        .join(Subject, Subject.id == BookEdition.subject_id)
        .where(Grade.number == 11, Subject.code == "biology", Chapter.retired_at.is_(None))
        .order_by(Chapter.display_order)
    ).all()[1]
    book = db.get(BookEdition, chapter.book_id)
    refs = [
        {
            "source_document_id": str(book.source_document_id),
            "pdf_from": chapter.pdf_start or 1,
            "pdf_to": chapter.pdf_start or 1,
            "note": "technical fixture",
        }
    ]
    for old in db.scalars(
        select(ContentItem).where(
            ContentItem.chapter_id == chapter.id,
            ContentItem.availability == "live",
            ContentItem.title.like(f"{FIXTURE_PREFIX} {TITLE}%"),
        )
    ):
        old.availability = "retired"  # one fixture question in the chapter at a time
    ids: dict[str, uuid.UUID] = {}
    for kind, title, parent in (("written", f"{TITLE} question", None), ("rubric", f"{TITLE} rubric", "q")):
        item = ContentItem(
            id=uuid.uuid4(),
            kind=kind,
            chapter_id=chapter.id,
            grade_number=11,
            subject_code="biology",
            title=f"{FIXTURE_PREFIX} {title}",
            state="published",
            availability="unpublished",
            created_by=author,
            family_id=None,
            parent_item_id=ids["q"] if parent else None,
            access_tier="premium",
        )
        if kind == "written":
            item.family_id = item.id
        db.add(item)
        db.flush()
        if kind == "written":
            body: dict[str, Any] = {
                "question_type": "short",
                "stem": _p(
                    "Technical fixture question for the rubric-correction journey. This is not academic content."
                ),
                "subparts": [
                    {"id": "a", "label": "(a)", "blocks": _p("Fixture part a."), "max_units": 200},
                    {"id": "b", "label": "(b)", "blocks": _p("Fixture part b."), "max_units": 300},
                ],
                "max_units": 500,
                "answer_language": "en",
                "expected_structures": [],
                "origin": "original_practice",
            }
        else:
            body = _rubric(ids["qv"])
        v = _version(item.id, 1, body, author, kind)
        v.source_refs = refs
        db.add(v)
        db.flush()
        item.working_version_id = item.published_version_id = v.id
        item.availability = "live"
        ids["q" if kind == "written" else "r"] = item.id
        ids["qv" if kind == "written" else "rv"] = v.id
        record(
            db,
            actor=None,
            action="content.dev_fixture_published",
            target_type="content_item",
            target_id=str(item.id),
            details={"via": "portal-dev-fixture-rubric-correction", "note": "technical fixture"},
        )
    return {
        "chapter_id": str(chapter.id),
        "chapter_title": chapter.title,
        "question_item_id": str(ids["q"]),
        "rubric_item_id": str(ids["r"]),
        "rubric_v1": str(ids["rv"]),
    }


def _correct(db: Any, author: uuid.UUID, rubric_id: uuid.UUID, kind: str) -> dict[str, Any]:
    item = db.get(ContentItem, rubric_id)
    if item is None or item.kind != "rubric" or not item.title.startswith(FIXTURE_PREFIX):
        raise SystemExit("not a fixture rubric")
    current = db.get(ContentVersion, item.published_version_id)
    body = copy.deepcopy(current.body)
    if kind == "scoring":
        body["criteria"][0]["description"] = f"Fixture criterion for part a, corrected (v{current.number + 1})"
    else:
        body["expected_concepts"].append(f"Fixture concept added in v{current.number + 1}")
    v = _version(item.id, current.number + 1, body, author, "rubric")
    v.source_refs = current.source_refs
    current.status = "superseded"
    db.add(v)
    db.flush()
    item.working_version_id = item.published_version_id = v.id
    record(
        db,
        actor=None,
        action="content.dev_fixture_published",
        target_type="content_item",
        target_id=str(item.id),
        details={"via": "portal-dev-fixture-rubric-correction", "version": v.number, "kind": kind},
    )
    return {"rubric_item_id": str(item.id), "published_version": str(v.id), "number": v.number}


if __name__ == "__main__":
    sys.exit(main())
