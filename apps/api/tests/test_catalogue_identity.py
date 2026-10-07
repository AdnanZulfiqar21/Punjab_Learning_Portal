"""Catalogue corrections against an already-populated database (no reset): stable IDs, retirement, reactivation.

The modified catalogue mimics what content/tools/build_catalogue.py emits after reconciliation (IMPL-08): corrected
entities keep their IDs; removed ones disappear from `books` and are listed in `retired`.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from portal_api.modules.curriculum.importer import DEFAULT_CATALOGUE, DEFAULT_REGISTRY, run_import
from portal_api.modules.curriculum.models import Chapter, ImportBatch, Topic


def _walk(ts: list[dict[str, Any]]):
    for t in ts:
        yield t
        yield from _walk(t["children"])


def test_corrections_keep_ids_and_removals_retire_without_reset(
    client: TestClient, db: Session, tmp_path: Path
) -> None:
    original = json.loads(DEFAULT_CATALOGUE.read_text(encoding="utf-8"))
    batches_before = db.scalar(select(func.count()).select_from(ImportBatch))
    rows_before = db.scalar(select(func.count()).select_from(Topic))
    cat = copy.deepcopy(original)
    bio11 = next(b for b in cat["books"] if b["source_id"] == "C11-BIO")
    ch6 = next(c for c in bio11["chapters"] if c["number"] == 6)
    photo = next(t for t in _walk(ch6["topics"]) if t["title"].startswith("Photosynthesis"))
    # 1) reviewer corrections: printed number and title fixed, numbered/unnumbered changed elsewhere
    photo["title"], photo["number"] = "Photosynthesis", "6.1"
    unnumbered = next(t for t in _walk(ch6["topics"]) if t["number"] is None)
    unnumbered["number"] = "6.0"
    # 2) a topic removed from the source index and its whole chapter tail reordered
    removed = ch6["topics"].pop()
    removed_ids = {t["id"] for t in _walk([removed])}
    ch6["topics"].reverse()  # reorder: must not collide with the per-chapter active display-order uniqueness
    # 3) an entire chapter removed (e.g. found to be a duplicate in the file)
    removed_chapter = bio11["chapters"].pop()
    cat["retired"] = {i: {"kind": "topic"} for i in removed_ids} | {removed_chapter["id"]: {"kind": "chapter"}}
    path = tmp_path / "catalogue.json"
    path.write_text(json.dumps(cat), encoding="utf-8")

    batch = run_import(db, path, DEFAULT_REGISTRY, apply=True)
    assert batch.status == "APPLIED", batch.errors
    assert batch.counts["topics_new"] == 0 and batch.counts["chapters_new"] == 0
    assert batch.counts["retire_chapters"] == 1 and batch.counts["retire_topics"] >= len(removed_ids)

    # Same IDs, corrected values.
    ch = client.get(f"/v1/chapters/{ch6['id']}").json()
    flat = {t["id"]: t for t in _walk(ch["topics"])}
    assert flat[photo["id"]]["title"] == "Photosynthesis" and flat[photo["id"]]["number"] == "6.1"
    assert flat[unnumbered["id"]]["number"] == "6.0"
    assert not (removed_ids & set(flat)), "retired topics must not be shown"
    # Retired rows still exist (historical references stay valid); nothing was deleted.
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(Topic)) == rows_before
    assert all(db.get(Topic, __import__("uuid").UUID(i)).retired_at is not None for i in removed_ids)
    # Retired chapter: hidden from the book, explicit 410 when addressed directly, absent from search.
    book = client.get("/v1/grades/11/subjects/biology/book").json()
    assert removed_chapter["id"] not in {c["id"] for c in book["chapters"]}
    gone = client.get(f"/v1/chapters/{removed_chapter['id']}")
    assert gone.status_code == 410 and gone.json()["title"] == "GONE"
    hits = client.get("/v1/search", params={"q": removed_chapter["title"][:20], "grade": 11}).json()["hits"]
    assert removed_chapter["id"] not in {h["chapter_id"] for h in hits}

    # Restoring the original catalogue reactivates the very same IDs.
    restore = run_import(db, DEFAULT_CATALOGUE, DEFAULT_REGISTRY, apply=True)
    assert restore.status == "APPLIED"
    assert restore.counts["reactivate_chapters"] == 1 and restore.counts["reactivate_topics"] >= len(removed_ids)
    assert client.get(f"/v1/chapters/{removed_chapter['id']}").status_code == 200
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(Chapter).where(Chapter.retired_at.is_not(None))) == 0
    assert db.scalar(select(func.count()).select_from(ImportBatch)) == batches_before + 2


def test_reimport_never_resets_academic_content_state(db: Session) -> None:
    chapter = db.scalars(select(Chapter).where(Chapter.retired_at.is_(None))).first()
    assert chapter is not None
    chapter.content_state = "IN_REVIEW"
    db.commit()
    run_import(db, DEFAULT_CATALOGUE, DEFAULT_REGISTRY, apply=True)
    db.expire_all()
    assert db.get(Chapter, chapter.id).content_state == "IN_REVIEW"
    chapter = db.get(Chapter, chapter.id)
    chapter.content_state = "SOURCE_INDEXED"
    db.commit()
