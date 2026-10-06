"""Importer conventions: dry run first, validation, idempotent upsert, never silently merging grades."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from portal_api.modules.curriculum.importer import DEFAULT_CATALOGUE, DEFAULT_REGISTRY, run_import
from portal_api.modules.curriculum.models import Chapter, ImportBatch, Topic


def test_reimport_is_idempotent(db: Session) -> None:
    before = (db.scalar(select(func.count()).select_from(Chapter)), db.scalar(select(func.count()).select_from(Topic)))
    batch = run_import(db, DEFAULT_CATALOGUE, DEFAULT_REGISTRY, apply=True)
    assert batch.status == "APPLIED"
    assert batch.counts["chapters_new"] == 0 and batch.counts["topics_new"] == 0
    after = (db.scalar(select(func.count()).select_from(Chapter)), db.scalar(select(func.count()).select_from(Topic)))
    assert before == after == (122, batch.counts["topics"])


def test_dry_run_writes_nothing(db: Session) -> None:
    n = db.scalar(select(func.count()).select_from(ImportBatch))
    batch = run_import(db, DEFAULT_CATALOGUE, DEFAULT_REGISTRY, apply=False)
    assert batch.status == "DRY_RUN_OK" and batch.errors == []
    assert db.scalar(select(func.count()).select_from(ImportBatch)) == n


def _malformed(tmp_path: Path, mutate) -> tuple[Path, Path]:  # type: ignore[no-untyped-def]
    cat = json.loads(DEFAULT_CATALOGUE.read_text(encoding="utf-8"))
    reg = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
    mutate(cat, reg)
    c, r = tmp_path / "catalogue.json", tmp_path / "registry.json"
    c.write_text(json.dumps(cat), encoding="utf-8")
    r.write_text(json.dumps(reg), encoding="utf-8")
    return c, r


def test_rejects_book_whose_grade_disagrees_with_its_source(db: Session, tmp_path: Path) -> None:
    def mutate(cat, reg):  # type: ignore[no-untyped-def]
        cat["books"][0]["grade"] = 12 if cat["books"][0]["grade"] == 11 else 11

    c, r = _malformed(tmp_path, mutate)
    batch = run_import(db, c, r, apply=False)
    assert batch.status == "REJECTED"
    assert any("grade/subject disagrees" in e for e in batch.errors)


def test_rejects_duplicate_ids_and_unknown_schema(db: Session, tmp_path: Path) -> None:
    def mutate(cat, reg):  # type: ignore[no-untyped-def]
        chs = cat["books"][0]["chapters"]
        chs[1]["id"] = chs[0]["id"]
        cat["schema_version"] = 99

    c, r = _malformed(tmp_path, mutate)
    batch = run_import(db, c, r, apply=False)
    assert batch.status == "REJECTED"
    assert any("duplicate id" in e for e in batch.errors)
    assert any("schema_version" in e for e in batch.errors)
