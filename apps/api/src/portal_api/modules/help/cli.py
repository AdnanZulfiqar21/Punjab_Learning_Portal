"""portal-help-import [DIR]: import help articles from Markdown files as drafts (P15.S2.T1).

Each file is ``<locale>/<slug>.md`` with a small header::

    ---
    title: Upload limits for written answers
    summary: Which files you can upload and how many pages a test accepts.
    tags: written, upload
    ---
    Body in the Markdown subset (headings, lists, "> " notes, paragraphs).

Importing only creates or updates *draft* versions (unchanged files create nothing). Help-centre staff review and
publish them in the studio, with an MFA session. Nothing is published by this command.
"""

from __future__ import annotations

import sys
from pathlib import Path

from portal_api.db import get_sessionmaker
from portal_api.modules.help import service

DEFAULT_DIR = Path(__file__).resolve().parents[4] / "help_articles"


def parse(path: Path) -> dict[str, object]:
    raw = path.read_text(encoding="utf8")
    if not raw.startswith("---\n"):
        raise ValueError(f"{path}: missing the --- header")
    head, body = raw[4:].split("\n---\n", 1)
    meta = dict(line.split(":", 1) for line in head.splitlines() if ":" in line)
    meta = {k.strip(): v.strip() for k, v in meta.items()}
    return {
        "slug": path.stem,
        "locale": path.parent.name,
        "title": meta["title"],
        "summary": meta["summary"],
        "tags": [t.strip() for t in meta.get("tags", "").split(",") if t.strip()],
        "markdown": body.strip(),
    }


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    root = Path(args[0]) if args else DEFAULT_DIR
    files = sorted(root.glob("*/*.md"))
    with get_sessionmaker()() as db:
        for f in files:
            a = parse(f)
            service.save_draft(db, None, **a)  # type: ignore[arg-type]
    print(f"help articles imported as drafts: {len(files)} file(s) from {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
