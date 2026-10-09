"""Catalogue management (roadmap P06.S1.T1; CATALOGUE-ADMIN-01).

The class/subject/chapter/topic structure comes from the owner's books through the derived catalogue
(`content/catalogue/catalogue.json`, built from the read-only sources by `content/tools/build_catalogue.py`). It is
changed by editing and rebuilding that reviewed catalogue, never by free-form edits in the browser, which the next
import would silently undo and which would drift from the source pages. Staff with `manage_catalogue` (owner/admin,
MFA) manage it here:

* **Preview** shows exactly what applying the current catalogue would do (chapters and topics added, retired,
  reactivated, renamed, moved and reordered) and the content that depends on each affected chapter or topic, flagging
  what learners can see now (live) and anything published.
* **Apply** runs the import only if the catalogue is byte-identical to the one previewed (its SHA-256), and only with
  explicit acknowledgement when published content depends on a retiring or moving chapter or topic. Nothing is ever
  deleted: retired structure is kept for history and hidden from learners, and reapplying an earlier catalogue
  reactivates it. Both steps are audited.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from portal_api.db import get_session
from portal_api.errors import Conflict, Unprocessable
from portal_api.modules.audit.models import record
from portal_api.modules.curriculum import importer
from portal_api.modules.identity.deps import Principal, require
from portal_api.modules.identity.permissions import Permission


def _paths() -> tuple[Path, Path]:
    return (
        Path(os.environ.get("PORTAL_CATALOGUE_PATH") or importer.DEFAULT_CATALOGUE),
        Path(os.environ.get("PORTAL_SOURCE_REGISTRY_PATH") or importer.DEFAULT_REGISTRY),
    )


def _dependencies(db: Session, changes: dict[str, Any]) -> list[dict[str, Any]]:
    """Content linked to a chapter or topic that would be retired or moved to another chapter."""
    from portal_api.modules.content.models import ContentItem

    chapters = {uuid.UUID(c["id"]): "chapter retired" for c in changes.get("chapters_retired", [])}
    topics = {uuid.UUID(t["id"]): "topic retired" for t in changes.get("topics_retired", [])}
    topics |= {uuid.UUID(t["id"]): "topic moved to another chapter" for t in changes.get("topics_moved", [])
               if t["from_chapter"] != t["to_chapter"]}  # fmt: skip
    if not chapters and not topics:
        return []
    conds = []
    if chapters:
        conds.append(ContentItem.chapter_id.in_(chapters))
    if topics:
        conds.append(ContentItem.topic_id.in_(topics))
    out = []
    for item in db.scalars(select(ContentItem).where(or_(*conds)).order_by(ContentItem.kind, ContentItem.title)):
        reason = chapters.get(item.chapter_id) or topics.get(item.topic_id)  # type: ignore[arg-type]
        out.append(
            {
                "item_id": str(item.id),
                "kind": item.kind,
                "title": item.title,
                "availability": item.availability,
                "published": item.published_version_id is not None,
                "reason": reason,
            }
        )
    return out


def preview(db: Session, who: Principal) -> dict[str, Any]:
    catalogue, registry = _paths()
    p = importer.plan(db, catalogue, registry)
    deps = _dependencies(db, p["changes"]) if not p["errors"] else []
    out = {
        "input_sha256": p["input_sha256"],
        "errors": p["errors"],
        "changes": p["changes"],
        "dependencies": deps,
        "published_dependencies": sum(1 for d in deps if d["published"]),
        "change_count": sum(len(v) for v in p["changes"].values()),
    }
    record(
        db,
        actor=who.user.id,
        action="catalogue.previewed",
        target_type="catalogue",
        target_id=p["input_sha256"][:16],
        details={k: len(v) for k, v in p["changes"].items() if v} | {"errors": len(p["errors"])},
    )
    db.commit()
    return out


def apply(db: Session, who: Principal, input_sha256: str, acknowledge_dependencies: bool) -> dict[str, Any]:
    catalogue, registry = _paths()
    current = importer.plan(db, catalogue, registry)
    if current["input_sha256"] != input_sha256:
        raise Conflict(
            "The catalogue changed since your preview. Preview it again before applying.",
            code_reason="CATALOGUE_CHANGED",
        )
    if current["errors"]:
        raise Unprocessable("The catalogue doesn't validate.", errors=current["errors"])
    deps = _dependencies(db, current["changes"])
    published = [d for d in deps if d["published"]]
    if published and not acknowledge_dependencies:
        raise Conflict(
            "Published content depends on chapters or topics this change retires or moves. Review them and "
            "acknowledge before applying.",
            code_reason="DEPENDENCIES_UNACKNOWLEDGED",
            dependencies=published,
        )
    db.rollback()  # the planning reads end here; the import runs in its own transaction
    batch = importer.run_import(db, catalogue, registry, apply=True)
    if batch.status != "APPLIED":
        raise Unprocessable("The catalogue couldn't be applied.", errors=batch.errors)
    record(
        db,
        actor=who.user.id,
        action="catalogue.applied",
        target_type="import_batch",
        target_id=str(batch.id),
        details={
            "input_sha256": input_sha256,
            "changes": {k: len(v) for k, v in current["changes"].items() if v},
            "published_dependencies": [d["item_id"] for d in published],
        },
    )
    db.commit()
    return {"batch_id": str(batch.id), "status": batch.status, "counts": batch.counts}


# ------------------------------------------------------------------ routes


router = APIRouter(prefix="/v1/admin/catalogue", tags=["catalogue admin"])
DB = Annotated[Session, Depends(get_session)]
CatalogueAdmin = Annotated[Principal, Depends(require(Permission.manage_catalogue))]


class CatalogueDependency(BaseModel):
    item_id: uuid.UUID
    kind: str
    title: str
    availability: str
    published: bool
    reason: str


class CataloguePreview(BaseModel):
    input_sha256: str
    errors: list[str]
    changes: dict[str, list[dict[str, Any]]]
    dependencies: list[CatalogueDependency]
    published_dependencies: int
    change_count: int


class CatalogueApplyIn(BaseModel):
    input_sha256: str = Field(min_length=64, max_length=64)
    acknowledge_dependencies: bool = False


class CatalogueApplied(BaseModel):
    batch_id: uuid.UUID
    status: str
    counts: dict[str, int]


@router.post("/preview", response_model=CataloguePreview, summary="What applying the current catalogue would change")
def catalogue_preview(db: DB, who: CatalogueAdmin, response: Response) -> CataloguePreview:
    response.headers["Cache-Control"] = "private, no-store"
    return CataloguePreview(**preview(db, who))


@router.post("/apply", response_model=CatalogueApplied, summary="Apply the previewed catalogue (MFA; audited)")
def catalogue_apply(db: DB, who: CatalogueAdmin, body: CatalogueApplyIn) -> CatalogueApplied:
    return CatalogueApplied(**apply(db, who, body.input_sha256, body.acknowledge_dependencies))
