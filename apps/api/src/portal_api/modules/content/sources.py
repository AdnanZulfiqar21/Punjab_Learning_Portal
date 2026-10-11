"""Safe source-document intake (roadmap P06.S2.T3; SOURCE-INTAKE-01).

The owner's textbook PDFs are registered in the catalogue with their SHA-256 (the file itself never enters the public
repository, IMPL-01). Intake stores the **exact registered original** privately so reviewers can see the page a claim
cites:

* Only the owner (owner_admin, MFA) uploads an original, and only bytes whose SHA-256 equals the registered checksum are
  accepted. Anything else is refused, so the stored copy is always the owner's unchanged original. A stored original is
  immutable: it is written once under its hash and never replaced or edited.
* Content staff in the source's class and subject can view one PDF page at a time, rendered to PNG in an isolated,
  time-limited worker process (PDFium), never the PDF itself. Rendered pages are cached by hash and page.
* Extraction/OCR is not done here; when it is, its output is an untrusted draft that needs human checking.

Storage is the private asset directory (`PORTAL_ASSET_DIR/sources/`) until object storage exists (B03).
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi import Path as PathParam
from pydantic import BaseModel
from sqlalchemy.orm import Session

from portal_api.db import get_session
from portal_api.errors import NotFound, TooLarge, Unprocessable
from portal_api.modules.audit.models import record
from portal_api.modules.content.router import studio_member
from portal_api.modules.curriculum.models import SourceDocument
from portal_api.modules.identity.deps import Principal, require
from portal_api.modules.identity.permissions import Permission

MAX_BYTES = 300 * 1024 * 1024
RENDER_TIMEOUT_S = 30
RENDER_MAX_SIDE_PX = 2200


def _dir(*parts: str) -> Path:
    from portal_api.modules.content.assets import _root

    d = _root().joinpath("sources", *parts)
    d.mkdir(parents=True, exist_ok=True)
    return d


def original_path(doc: SourceDocument) -> Path:
    return _dir() / f"{doc.sha256}.pdf"


def has_original(doc: SourceDocument) -> bool:
    return original_path(doc).is_file()


def _doc(db: Session, source_id: uuid.UUID) -> SourceDocument:
    doc = db.get(SourceDocument, source_id)
    if doc is None:
        raise NotFound("Source not found.")
    return doc


def store_original(db: Session, who: Principal, source_id: uuid.UUID, tmp: Path, sha: str, size: int) -> dict[str, Any]:
    """Accept a fully received upload only if it is byte-for-byte the registered original."""
    doc = _doc(db, source_id)
    if sha != doc.sha256:
        tmp.unlink(missing_ok=True)
        raise Unprocessable(
            "This file isn't the registered original: its SHA-256 differs from the catalogue's record.",
            code_reason="NOT_THE_ORIGINAL",
            expected_sha256=doc.sha256,
            received_sha256=sha,
        )
    target = original_path(doc)
    if target.is_file():
        tmp.unlink(missing_ok=True)  # already stored; originals are written once and never replaced
        stored = False
    else:
        os.replace(tmp, target)
        os.chmod(target, 0o440)
        stored = True
    record(db, actor=who.user.id, action="source.original_stored" if stored else "source.original_confirmed",
           target_type="source_document", target_id=str(doc.id), details={"sha256": sha, "bytes": size})  # fmt: skip
    db.commit()
    return {"source_id": doc.id, "sha256": sha, "bytes": size, "stored": stored}


def _scope_ok(db: Session, who: Principal, doc: SourceDocument) -> bool:
    from portal_api.modules.content.workflow import roles_in_scope

    return bool(roles_in_scope(db, who.user.id, doc.grade_number, doc.subject_code))


def page_png(db: Session, who: Principal, source_id: uuid.UUID, page: int) -> bytes:
    doc = _doc(db, source_id)
    if not _scope_ok(db, who, doc):
        raise NotFound("Source not found.")  # outside the caller's class and subject
    if not 1 <= page <= max(1, doc.pdf_pages):
        raise NotFound(f"This source has {doc.pdf_pages} PDF pages.")
    if not has_original(doc):
        raise NotFound("The original of this source hasn't been stored yet. The owner can upload it.")
    cached = _dir("pages", doc.sha256) / f"{page}.png"
    if cached.is_file():
        return cached.read_bytes()
    png = _render(original_path(doc), page - 1)
    cached.write_bytes(png)
    return png


def _render(pdf: Path, index: int) -> bytes:
    """Render one page in a separate, time-limited process (the API process never parses the PDF itself)."""
    with tempfile.TemporaryDirectory(prefix="portal-source-") as tmp:
        out = Path(tmp) / "page.png"
        env = {k: v for k, v in os.environ.items() if k in ("PATH", "SYSTEMROOT", "TEMP", "TMP")}
        try:
            proc = subprocess.run(  # noqa: S603 - fixed interpreter and module, no shell, server-controlled paths
                [sys.executable, "-I", "-m", "portal_api.modules.content.sources", str(pdf), str(index), str(out)],
                capture_output=True,
                timeout=RENDER_TIMEOUT_S,
                env=env,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            raise Unprocessable("This page took too long to render.") from e
        if proc.returncode != 0 or not out.is_file():
            raise Unprocessable("This page couldn't be rendered.")
        return out.read_bytes()


def _child(pdf: str, index: int, out: str) -> None:  # pragma: no cover - runs in the isolated worker
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(pdf)
    try:
        page = doc[index]
        w, h = page.get_size()
        scale = min(RENDER_MAX_SIDE_PX / max(w, h), 3.0)
        page.render(scale=scale).to_pil().convert("RGB").save(out, format="PNG", optimize=True)
    finally:
        doc.close()


# ------------------------------------------------------------------ routes
router = APIRouter(prefix="/v1/studio", tags=["studio"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[Principal, Depends(require(Permission.confirm_source_rights))]  # the owner (MFA), as for rights
Member = Annotated[Principal, Depends(studio_member)]  # content staff: authors and reviewers


class OriginalOut(BaseModel):
    source_id: uuid.UUID
    sha256: str
    bytes: int
    stored: bool


@router.post(
    "/sources/{source_id}/original",
    response_model=OriginalOut,
    summary="Store the owner's original (raw PDF body); only the registered SHA-256 is accepted",
)
async def upload_original(db: DB, who: Owner, source_id: uuid.UUID, request: Request) -> OriginalOut:
    from fastapi.concurrency import run_in_threadpool

    _doc(db, source_id)
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_BYTES:
        raise TooLarge("A source PDF can be at most 300 MB.")
    digest, size = hashlib.sha256(), 0
    fd, name = tempfile.mkstemp(prefix="source-", suffix=".part", dir=_dir("incoming"))
    tmp = Path(name)
    try:
        with os.fdopen(fd, "wb") as f:
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_BYTES:
                    raise TooLarge("A source PDF can be at most 300 MB.")
                digest.update(chunk)
                f.write(chunk)
        return OriginalOut(**await run_in_threadpool(store_original, db, who, source_id, tmp, digest.hexdigest(), size))
    finally:
        tmp.unlink(missing_ok=True)


@router.get("/sources/{source_id}/pages/{page}", summary="One PDF page of a stored original, as PNG (content staff)")
def source_page(db: DB, who: Member, source_id: uuid.UUID, page: Annotated[int, PathParam(ge=1, le=5000)]) -> Response:
    return Response(
        content=page_png(db, who, source_id, page),
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"},
    )


if __name__ == "__main__":  # pragma: no cover - the isolated render worker
    _child(sys.argv[1], int(sys.argv[2]), sys.argv[3])
