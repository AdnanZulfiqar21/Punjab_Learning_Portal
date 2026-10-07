"""Development/test-only practice fixtures (portal-dev-seed-practice).

Creates a handful of clearly labelled technical-fixture MCQs in one Class XI Biology chapter and marks them live, so
the learner practice journey (form → attempt → saves → submit → results) can be exercised end to end in local
development and in CI's disposable database. The text says it is a technical fixture and is not academic content.

This deliberately bypasses review and the publication-rights gate, which is why it is refused unless the role is
development/test *and* the development identity adapter is enabled (both are refused in staging/production by the
configuration validator). It is idempotent: existing fixtures are left as they are.
"""

from __future__ import annotations

import sys
import uuid

from sqlalchemy import select

from portal_api.config import get_settings
from portal_api.db import get_sessionmaker
from portal_api.modules.audit.models import record
from portal_api.modules.content import blocks
from portal_api.modules.content.models import ContentItem, ContentVersion
from portal_api.modules.curriculum.models import BookEdition, Chapter, Grade, Subject
from portal_api.modules.identity.models import AppUser

FIXTURE_PREFIX = "[FIXTURE]"
COUNT = 8
WRITTEN_COUNT = 2
NAMESPACE = uuid.UUID("6f0f3a52-7d0f-4a8b-9c1e-0c5b8a0d4e11")  # deterministic fixture IDs


def _p(text: str) -> list[dict[str, object]]:
    return [{"type": "paragraph", "text": text}]


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    if settings.role not in ("development", "test") or not settings.dev_auth_enabled:
        print(
            "refusing: practice fixtures exist only for development/test with the dev identity adapter", file=sys.stderr
        )
        return 2
    with get_sessionmaker()() as db:
        chapter = db.scalars(
            select(Chapter)
            .join(BookEdition, BookEdition.id == Chapter.book_id)
            .join(Grade, Grade.id == BookEdition.grade_id)
            .join(Subject, Subject.id == BookEdition.subject_id)
            .where(Grade.number == 11, Subject.code == "biology", Chapter.retired_at.is_(None))
            .order_by(Chapter.display_order)
        ).first()
        author = db.scalar(select(AppUser).where(AppUser.email == "studio-author@example.com"))
        if chapter is None or author is None:
            print("run portal-import-catalogue --apply and portal-dev-seed-staff first", file=sys.stderr)
            return 1
        book = db.get(BookEdition, chapter.book_id)
        assert book is not None
        created = 0
        refs = [
            {
                "source_document_id": str(book.source_document_id),
                "pdf_from": chapter.pdf_start or 1,
                "pdf_to": chapter.pdf_start or 1,
                "note": "technical fixture",
            }
        ]

        def publish(name: str, kind: str, title: str, body: dict[str, object], parent: uuid.UUID | None = None) -> bool:
            item_id = uuid.uuid5(NAMESPACE, name)
            if db.get(ContentItem, item_id) is not None:
                return False
            version_id = uuid.uuid5(NAMESPACE, f"{name}-v1")
            db.add(
                ContentItem(
                    id=item_id,
                    kind=kind,
                    chapter_id=chapter.id,
                    grade_number=11,
                    subject_code="biology",
                    title=f"{FIXTURE_PREFIX} {title}",
                    state="published",
                    availability="unpublished",  # becomes live once its version exists (constraint order)
                    created_by=author.id,
                    family_id=item_id if kind in ("mcq", "written") else None,
                    parent_item_id=parent,
                )
            )
            db.flush()
            db.add(
                ContentVersion(
                    id=version_id,
                    item_id=item_id,
                    number=1,
                    status="published",
                    revision=1,
                    content_schema_version=blocks.CONTENT_SCHEMA_VERSION,
                    body=body,
                    block_types=["paragraph"] if kind != "rubric" else [],
                    source_refs=refs,
                    change_reason=None,
                    created_by=author.id,
                    contributors=[str(author.id)],
                    updated_by=author.id,
                )
            )
            db.flush()
            item = db.get(ContentItem, item_id)
            assert item is not None
            item.working_version_id = version_id
            item.published_version_id = version_id
            item.availability = "live"
            record(
                db,
                actor=None,
                action="content.dev_fixture_published",
                target_type="content_item",
                target_id=str(item_id),
                details={
                    "via": "portal-dev-seed-practice",
                    "note": "technical fixture; bypasses review in dev/test only",
                },
            )
            return True

        for i in range(1, COUNT + 1):
            key = f"o{(i - 1) % 4 + 1}"
            body: dict[str, object] = {
                "stem": _p(f"Technical fixture question {i}. This is not academic content. Which option is {key}?"),
                "options": [{"id": f"o{n}", "blocks": _p(f"Fixture option o{n}")} for n in range(1, 5)],
                "correct_option_id": key,
                "marks": 1,
                "shuffle_options": True,
                "explanation": {"correct": _p(f"Fixture explanation: the fixture key is {key}."), "distractors": {}},
                "metadata": {},
                "origin": "original_practice",
                "language": "en",
            }
            created += publish(f"practice-fixture-{i}", "mcq", f"Practice question {i}", body)

        # Written questions with reconciled rubrics, so the written-practice journey can run in dev/CI.
        for i in range(1, WRITTEN_COUNT + 1):
            q_name = f"written-fixture-{i}"
            q_body: dict[str, object] = {
                "question_type": "short",
                "stem": _p(f"Technical fixture written question {i}. This is not academic content."),
                "subparts": [
                    {"id": "a", "label": "(a)", "blocks": _p("Fixture part a."), "max_units": 200},
                    {"id": "b", "label": "(b)", "blocks": _p("Fixture part b."), "max_units": 300},
                ],
                "max_units": 500,
                "answer_language": "en",
                "expected_structures": [],
                "origin": "original_practice",
            }
            created += publish(q_name, "written", f"Written question {i}", q_body)
            r_body: dict[str, object] = {
                "question_version_id": str(uuid.uuid5(NAMESPACE, f"{q_name}-v1")),
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
            created += publish(
                f"{q_name}-rubric",
                "rubric",
                f"Rubric for written question {i}",
                r_body,
                parent=uuid.uuid5(NAMESPACE, q_name),
            )
        db.commit()
    total = COUNT + 2 * WRITTEN_COUNT
    print(f"practice fixtures: {created} created, {total - created} already present (Class XI Biology, first chapter)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
