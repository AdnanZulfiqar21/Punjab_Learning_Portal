"""Operational commands for written evidence (review R01/R02).

portal-written-previews        # render previews for pages migrated before previews existed (idempotent)
portal-written-sweep-orphans   # remove stored objects no committed row references (older than one hour)
"""

from __future__ import annotations

import sys

from sqlalchemy import select

from portal_api.db import get_sessionmaker
from portal_api.modules.audit.models import record
from portal_api.modules.written import evidence, service, storage
from portal_api.modules.written.models import WrittenFile, WrittenPage


def previews(argv: list[str] | None = None) -> int:
    store = storage.get_store()
    done = failed = 0
    with get_sessionmaker()() as db:
        file_ids = db.scalars(select(WrittenPage.file_id).where(WrittenPage.preview_key.is_(None)).distinct()).all()
        for file_id in file_ids:
            f = db.get(WrittenFile, file_id)
            assert f is not None
            try:
                inspected = evidence.inspect(store.get(f.storage_key))
            except evidence.Rejected as e:
                # The original no longer passes validation: leave it without a preview (it can't be sealed or shown)
                # and report it; never invent a page.
                print(f"file {f.id}: {e.reason}", file=sys.stderr)
                failed += 1
                continue
            for page in service.pages_of_file(db, f.id):
                if page.preview_key is not None or page.page_index > len(inspected.pages):
                    continue
                lp = inspected.pages[page.page_index - 1]
                # Pre-R02 originals live at "<attempt>/<file id>" (a file, not a folder), so legacy previews are
                # siblings of it; new uploads use "<attempt>/<file id>/original" and ".../page-N.png".
                key = f"{f.attempt_id}/{f.id}.page-{page.page_index}.png"
                stored = store.put(key, lp.preview_png) if not store.exists(key) else None
                page.preview_key = key
                page.preview_sha256 = stored.sha256 if stored else store.sha256(key)
                page.width, page.height = lp.width, lp.height
                done += 1
            record(
                db, actor=None, action="written.previews_backfilled", target_type="written_file", target_id=str(f.id)
            )
            db.commit()
    print(f"previews rendered: {done}; files refused: {failed}")
    return 1 if failed else 0


def sweep(argv: list[str] | None = None) -> int:
    with get_sessionmaker()() as db:
        removed = service.sweep_orphans(db)
    print(f"orphaned objects removed: {len(removed)}")
    return 0


def repair(argv: list[str] | None = None) -> int:
    """portal-written-repair: idempotent, audited repairs for review findings (OCT8-02 pending obligations)."""
    from portal_api.modules.written import review

    with get_sessionmaker()() as db:
        fixed = review.repair_pending_obligations(db)
    print(f"pending-question obligations repaired: {len(fixed)}")
    return 0
