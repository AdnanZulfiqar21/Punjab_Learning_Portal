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
from sqlalchemy.orm import Session

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


def _fixture_png(label: str) -> bytes:
    import io

    from PIL import Image, ImageDraw

    im = Image.new("RGB", (640, 320), (240, 240, 240))
    draw = ImageDraw.Draw(im)
    draw.rectangle((40, 40, 600, 280), outline=(60, 60, 60), width=4)
    draw.text((70, 150), label, fill=(20, 20, 20))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _fixture_pdf() -> bytes:
    import io

    from PIL import Image, ImageDraw

    im = Image.new("RGB", (595, 842), (255, 255, 255))
    ImageDraw.Draw(im).text((60, 60), "Technical fixture handout. Not academic content.", fill=(0, 0, 0))
    buf = io.BytesIO()
    im.save(buf, format="PDF")
    return buf.getvalue()


def _fixture_asset(db: Session, author_id: uuid.UUID, kind: str, title: str, data: bytes) -> str:
    """Archive a synthetic fixture file as Class XI Biology (ASSETS-01) and return its version ID."""
    from portal_api.modules.content import assets

    asset = assets.Asset(kind=kind, title=f"{FIXTURE_PREFIX} {title}", grade_number=11, subject_code="biology",
                         created_by=author_id)  # fmt: skip
    db.add(asset)
    db.flush()
    derived = assets._derive(kind, data)
    version = assets.AssetVersion(id=uuid.uuid4(), asset_id=asset.id, number=1, created_by=author_id)
    version.master_key = f"{asset.id}/{version.id}/master"
    version.master_sha256 = assets._sha(data)
    version.master_bytes = len(data)
    version.media_type = derived["media_type"]
    version.width, version.height, version.pages = derived.get("width"), derived.get("height"), derived.get("pages")
    version.provenance = {"source": "Synthetic technical fixture (portal-dev-seed-practice)"}
    assets._write(version.master_key, data)
    assets._set_delivery(version, derived["delivery"], derived["delivery_type"])
    db.add(version)
    db.flush()
    return str(version.id)


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

        def publish(
            name: str,
            kind: str,
            title: str,
            body: dict[str, object],
            parent: uuid.UUID | None = None,
            access_tier: str = "premium",
        ) -> bool:
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
                    access_tier=access_tier,
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
                    block_types=blocks.validate_body(body, for_publication=False).block_types
                    if kind == "lesson"
                    else (["paragraph"] if kind not in ("rubric", "storyboard") else []),
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
        # One free-preview and one premium lesson, so lesson access (review R07) can be exercised end to end.
        for tier in ("preview", "premium"):
            created += publish(
                f"lesson-fixture-{tier}",
                "lesson",
                f"{tier.capitalize()} lesson",
                {"blocks": _p(f"Technical fixture {tier} lesson text. This is not academic content.")},
                access_tier=tier,
            )
        # P07.S1.T1: one free-preview lesson using every structured block, with synthetic archived assets, so the
        # lesson viewer can be checked in a browser (web, phone width) and on devices.
        if db.get(ContentItem, uuid.uuid5(NAMESPACE, "lesson-fixture-blocks")) is None:
            image = _fixture_asset(db, author.id, "image", "Fixture diagram", _fixture_png("Technical fixture diagram"))
            formula = _fixture_asset(db, author.id, "image", "Fixture formula rendering", _fixture_png("v = u + at"))
            sheet = _fixture_asset(db, author.id, "handout", "Fixture handout", _fixture_pdf())
            created += publish(
                "lesson-fixture-blocks",
                "lesson",
                "Structured blocks lesson",
                {
                    "blocks": [
                        {"type": "heading", "level": 2, "text": "Technical fixture: structured blocks"},
                        *_p("Technical fixture explanation text. This is not academic content."),
                        {
                            "type": "example",
                            "title": "Technical fixture worked example",
                            "problem": "Fixture problem statement (not academic content).",
                            "steps": ["Fixture step one.", "Fixture step two."],
                            "answer": "Fixture answer.",
                        },
                        {
                            "type": "equation",
                            "latex": "v = u + at",
                            "text_alt": "v equals u plus a t (fixture)",
                            "fallback": {
                                "text": "v = u + at",
                                "image_asset_id": formula,
                                "alt": "Fixture rendering of v equals u plus a t",
                                "reviewed": True,
                            },
                        },
                        {
                            "type": "diagram",
                            "asset_version_id": image,
                            "alt": "A synthetic fixture image with a box and a label",
                            "caption": "Technical fixture diagram",
                            "long_description": "A grey box with the words 'Technical fixture diagram'.",
                        },
                        {
                            "type": "table",
                            "caption": "Technical fixture table",
                            "header": ["Fixture column A", "Fixture column B"],
                            "rows": [["1", "2"], ["3", "4"]],
                        },
                        {"type": "callout", "tone": "warning", "text": "Technical fixture warning."},
                        {
                            "type": "checkpoint",
                            "mode": "self_check",
                            "prompt": "Technical fixture self-check prompt.",
                            "explanation": "Fixture explanation shown when revealed.",
                        },
                        {"type": "handout", "asset_version_id": sheet, "title": "Technical fixture handout"},
                    ]
                },
                access_tier="preview",
            )
        # P01.S4.T2 (RENDERER-SPIKE-01): notation the web typesets: a formula, chemistry, a formula whose link and class
        # the renderer must refuse, one that can't be typeset (its reviewed rendering shows), and an Urdu paragraph with
        # English words that must read right to left. Technical fixtures, not academic content.
        if db.get(ContentItem, uuid.uuid5(NAMESPACE, "lesson-fixture-notation")) is None:
            unparsable = _fixture_asset(
                db, author.id, "image", "Fixture rendering of a broken formula", _fixture_png("Fixture: broken formula")
            )

            def equation(latex: str, text_alt: str, image: str | None = None) -> dict[str, object]:
                fallback: dict[str, object] = {"text": text_alt, "reviewed": True}
                if image:
                    fallback |= {"image_asset_id": image, "alt": f"Fixture rendering: {text_alt}"}
                return {"type": "equation", "latex": latex, "text_alt": text_alt, "fallback": fallback}

            created += publish(
                "lesson-fixture-notation",
                "lesson",
                "Notation lesson",
                {
                    "blocks": [
                        {"type": "heading", "level": 2, "text": "Technical fixture: notation"},
                        equation(r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}", "Fixture formula: x equals a fraction"),
                        equation(r"\ce{2H2 + O2 -> 2H2O}", "Fixture chemistry: two H2 plus O2 gives two H2O"),
                        equation(
                            r"\href{javascript:alert(1)}{x} + \htmlClass{fixture-injected}{y}",
                            "Fixture: a formula whose link and class the renderer must refuse",
                        ),
                        equation(r"\frac{1}{", "Fixture: a formula that cannot be typeset", unparsable),
                        *_p(
                            "تکنیکی نمونہ: یہ پیراگراف اردو میں ہے، with English words in between. "
                            "Not academic content."
                        ),
                    ]
                },
                access_tier="preview",
            )
        # LECTURE-01: one published storyboard, so the lecture production workflow can be exercised end to end.
        created += publish(
            "storyboard-fixture",
            "storyboard",
            "Lecture storyboard",
            {
                "objective": "Technical fixture objective (not academic content)",
                "outcome": "Technical fixture outcome",
                "prerequisites": [],
                "duration_s": 40,
                "creative_direction": "Technical fixture direction",
                "scenes": [
                    {
                        "id": "s1",
                        "start_s": 0,
                        "end_s": 20,
                        "visual": "Fixture visual",
                        "narration": "Technical fixture narration one.",
                        "accessibility": "Fixture description of the visual.",
                        "claims": [{"text": "Fixture claim", "source_ref": 0}],
                    },
                    {
                        "id": "s2",
                        "start_s": 20,
                        "end_s": 40,
                        "visual": "Fixture summary",
                        "narration": "Technical fixture narration two.",
                        "accessibility": "Fixture description of the summary.",
                    },
                ],
            },
        )
        db.commit()
    total = COUNT + 2 * WRITTEN_COUNT + 5
    print(f"practice fixtures: {created} created, {total - created} already present (Class XI Biology, first chapter)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
