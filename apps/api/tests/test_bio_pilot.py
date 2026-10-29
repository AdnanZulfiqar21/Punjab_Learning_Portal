"""Class 11 Biology Chapter 1 pilot: language variants through the import, `model3d` figure references, and the topic
reader's language choice. Technical fixture bodies only; nothing here is academic content or a publication."""

from __future__ import annotations

import copy
import io
import json
import uuid
import zipfile
from typing import Any

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from portal_api.modules.content import assets, blocks
from portal_api.modules.content.models import ContentItem
from portal_api.modules.curriculum.models import Topic
from tests.test_content_import import _preview
from tests.test_content_workflow import Staff, _chapter, _refs

BIO = {"grades": [11], "subjects": ["biology"]}
PROVENANCE = {"source": "Fixture: drawn by the test suite", "licence": "Owner's own work", "tool": "test"}


def _png(colour: tuple[int, int, int]) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 6), colour).save(buf, format="PNG")
    return buf.getvalue()


def _pack(client: TestClient, author: Staff, names: list[str]) -> dict[str, str]:
    """Archive one fixture PNG per external id and return external id → version id."""
    items = [
        {"external_id": n, "kind": "image", "title": f"Fixture {n}", "file": f"{n}.png", "provenance": PROVENANCE}
        for n in names
    ]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "manifest.json",
            json.dumps({"schema_version": 1, "kind": "media", "grade": 11, "subject": "biology", "items": items}),
        )
        for i, n in enumerate(names):
            z.writestr(f"{n}.png", _png((10 + i, 120, 200)))
    r = client.post(
        "/v1/studio/assets/manifest?commit=true",
        headers={**author.headers, "Content-Type": "application/zip"},
        content=buf.getvalue(),
    )
    assert r.status_code == 200, r.text
    return {e["external_id"]: e["version_id"] for e in r.json()["entries"]}


def _body(poster: str, frames: list[str], image: str) -> dict[str, Any]:
    return {
        "blocks": [
            {"type": "heading", "level": 2, "text": "Fixture heading"},
            {"type": "paragraph", "text": "Technical fixture paragraph used only to exercise the pilot."},
            {
                "type": "model3d",
                "model": "fixture_model",
                "poster_asset_version_id": poster,
                "frames": frames,
                "alt": "A fixture model.",
                "caption": "Fixture caption.",
                "labels": ["Part A", "Part B"],
                "fallback": {
                    "text": "Fixture fallback text.",
                    "image_asset_id": image,
                    "alt": "Fixture still.",
                    "reviewed": True,
                },
            },
        ]
    }


def _lesson_doc(*rows: dict[str, Any]) -> bytes:
    return json.dumps({"schema_version": 1, "kind": "lesson", "items": list(rows)}).encode()


def _import(client: TestClient, author: Staff, *rows: dict[str, Any]) -> dict[str, Any]:
    r = _preview(client, author, _lesson_doc(*rows))
    assert r.status_code == 201, r.text
    batch = r.json()
    if any(row["errors"] for row in batch["rows"]):
        return batch
    done = client.post(f"/v1/studio/imports/{batch['id']}/commit", headers=author.headers)
    assert done.status_code == 200, done.text
    return dict(done.json())


def test_model3d_references_are_checked_like_diagrams() -> None:
    body = _body(
        "11111111-1111-4111-8111-111111111111",
        ["22222222-2222-4222-8222-222222222222"],
        "33333333-3333-4333-8333-333333333333",
    )
    refs = assets.block_refs(body)
    assert [(where, kind) for where, _vid, kind in refs] == [
        ("model3d poster", "image"),
        ("model3d frame 1", "image"),
        ("model3d fallback", "image"),
    ]
    # The block needs a reviewed fallback and renderer 2 on every platform, so older builds fall back (§5.4 rule 4).
    spec = blocks.REGISTRY["model3d"]
    assert spec.fallback_required_below and spec.min_renderer == {"web": 2, "android": 2, "ios": 2}


def test_a_roman_urdu_variant_imports_against_its_english_base_and_the_reader_picks_it(
    client: TestClient, db: Session
) -> None:
    chapter, doc = _chapter(db, 11, "biology", 3)  # its own chapter: other files draft into the first one
    topic = db.scalars(
        select(Topic)
        .where(Topic.chapter_id == chapter.id, Topic.parent_id.is_(None), Topic.retired_at.is_(None))
        .order_by(Topic.display_order)
    ).first()
    assert topic is not None
    author = Staff(client, db, ["content_author"], BIO)
    tag = uuid.uuid4().hex[:6]
    versions = _pack(
        client, author, [f"fx-{tag}-poster", f"fx-{tag}-frame-01", f"fx-{tag}-frame-02", f"fx-{tag}-still"]
    )
    body = _body(
        versions[f"fx-{tag}-poster"],
        [versions[f"fx-{tag}-frame-01"], versions[f"fx-{tag}-frame-02"]],
        versions[f"fx-{tag}-still"],
    )
    base = {
        "external_id": f"FX-{tag}-EN",
        "chapter": chapter.natural_key,
        "topic": str(topic.id),
        "title": f"Fixture pilot lesson {tag}",
        "source_refs": _refs(chapter, doc),
        "body": body,
    }
    roman = {
        **base,
        "external_id": f"FX-{tag}-RU",
        "title": f"Fixture pilot lesson {tag} (Roman Urdu)",
        "language": "roman_ur",
        "variant_of": f"FX-{tag}-EN",
    }
    del roman["topic"]  # the variant takes its topic from the base

    # A variant can't be imported before its base exists in the chapter.
    early = _import(client, author, roman)
    assert early["status"] != "committed"
    assert any("variant_of" in e for row in early["rows"] for e in row["errors"])

    # The base is checked against the archive at preview time, so a variant follows its base in a later import.
    first = _import(client, author, base)
    assert first["status"] == "committed" and first["rows"][0]["action"] == "create"
    second = _import(client, author, roman)
    assert second["status"] == "committed", second["rows"]
    assert second["rows"][0]["action"] == "create"

    with get_sessionmaker()() as session:
        en = session.scalar(select(ContentItem).where(ContentItem.external_ref == base["external_id"]))
        ru = session.scalar(select(ContentItem).where(ContentItem.external_ref == roman["external_id"]))
        assert en is not None and ru is not None
        assert en.language == "en" and ru.language == "roman_ur"
        assert ru.concept_id == en.id and ru.topic_id == en.topic_id == topic.id
        assert ru.translation_origin == "human"
        assert en.state == ru.state == "draft"  # drafts: publication still needs the independent review

    # A missing poster is a reference error, like a missing diagram.
    broken = copy.deepcopy(base)
    broken["external_id"] = f"FX-{tag}-BAD"
    broken["body"]["blocks"][2]["poster_asset_version_id"] = str(uuid.uuid4())
    bad = _import(client, author, broken)
    assert bad["status"] != "committed"
    assert any("poster" in e for row in bad["rows"] for e in row["errors"])

    # The topic reader (staff preview of drafts): English by default, Roman Urdu on request, and honest when missing.
    path = f"/v1/topics/{topic.id}/lesson"
    shown = client.get(path, headers=author.headers).json()
    assert shown["availability"] == "private_preview"
    assert shown["lesson"]["title"] == base["title"]
    assert shown["lesson"]["language"] == "en"
    assert shown["lesson"]["available_languages"] == ["en", "roman_ur"]
    ru_view = client.get(path, headers=author.headers, params={"language": "roman_ur"}).json()["lesson"]
    assert ru_view["language"] == "roman_ur" and ru_view["requested_language_missing"] is False
    assert ru_view["title"] == roman["title"]
    ur_view = client.get(path, headers=author.headers, params={"language": "ur"}).json()["lesson"]
    assert ur_view["language"] == "en" and ur_view["requested_language_missing"] is True
    # Both variants keep one block structure, so a reader can switch languages at the same place.
    en_types = [b["type"] for b in shown["lesson"]["body"]["blocks"]]
    assert [b["type"] for b in ru_view["body"]["blocks"]] == en_types
    # Learners never see a draft, in any language.
    learner = Staff(client, db, [])
    for params in ({}, {"language": "roman_ur"}):
        seen = client.get(path, headers=learner.headers, params=params).json()
        assert seen["lesson"] is None or seen["availability"] == "published"


def test_a_language_with_only_the_books_heading_is_shown_not_replaced(client: TestClient, db: Session) -> None:
    # Where the book prints only a heading (the topic's text is in its subtopics), the draft is that heading; the
    # reader shows it in the language asked for, rather than saying it is missing (BOOK-HEADING-01).
    chapter, doc = _chapter(db, 11, "biology", 10)
    topic = db.scalars(
        select(Topic)
        .where(Topic.chapter_id == chapter.id, Topic.parent_id.is_(None), Topic.retired_at.is_(None))
        .order_by(Topic.display_order)
    ).first()
    assert topic is not None
    author = Staff(client, db, ["content_author"], BIO)
    tag = uuid.uuid4().hex[:6]
    base = {
        "external_id": f"FX-{tag}-EN",
        "chapter": chapter.natural_key,
        "topic": str(topic.id),
        "title": f"Fixture heading-only lesson {tag}",
        "source_refs": _refs(chapter, doc),
        "body": {"blocks": [{"type": "heading", "level": 2, "text": "Fixture heading"}]},
    }
    assert _import(client, author, base)["status"] == "committed"
    path = f"/v1/topics/{topic.id}/lesson"
    alone = client.get(path, headers=author.headers).json()
    assert alone["availability"] == "private_preview"
    assert [b["text"] for b in alone["lesson"]["body"]["blocks"]] == ["Fixture heading"]

    roman = {
        **base,
        "external_id": f"FX-{tag}-RU",
        "title": f"Fixture heading-only lesson {tag} (Roman Urdu)",
        "language": "roman_ur",
        "variant_of": f"FX-{tag}-EN",
        "body": {"blocks": [{"type": "paragraph", "text": "Fixture explanation."}]},
    }
    del roman["topic"]
    assert _import(client, author, roman)["status"] == "committed"
    en = client.get(path, headers=author.headers, params={"language": "en"}).json()["lesson"]
    assert en["language"] == "en" and en["requested_language_missing"] is False
    assert en["available_languages"] == ["en", "roman_ur"]
    assert [b["type"] for b in en["body"]["blocks"]] == ["heading"]
