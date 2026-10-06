"""Build the source registry and curriculum catalogue from the verified per-book indexes (P22.S1).

Usage (from the project root):
    python content/tools/build_catalogue.py            # registry + catalogue (hashes PDFs if present)
    python content/tools/build_catalogue.py --check    # verify local PDFs still match registered checksums

Inputs : education_knowledge/indexes/class_<11|12>/<subject>/<slug>_book.json  (curated, verified indexes)
         <11|12> Class Data/*.pdf                                              (owner originals; local only)
Outputs: content/source_registry.json      one record per owner source (checksum, provenance, completeness)
         content/catalogue/catalogue.json  grades → subjects → books → chapters → topics, with stable IDs

Stable IDs are UUIDv5 values over a natural key (decision IMPL-04). Chapter numbers are display attributes.
Class XI and XII are separate books with separate IDs; nothing here merges them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import uuid
from pathlib import Path

PROJ = Path(__file__).resolve().parents[2]
INDEXES = PROJ / "education_knowledge" / "indexes"
OUT_REGISTRY = PROJ / "content" / "source_registry.json"
OUT_CATALOGUE = PROJ / "content" / "catalogue" / "catalogue.json"

# Fixed namespace for this product's curriculum identifiers. Never change it.
NAMESPACE = uuid.UUID("6f1d4c52-7a0b-5c1e-9a55-2b8f3d0e4a10")
REGION = "pk-punjab"
SCHEMA_VERSION = 1

GRADES = {11: {"code": "XI", "name": "Class XI (First Year)"}, 12: {"code": "XII", "name": "Class XII (Second Year)"}}
SUBJECTS = {
    "biology": {"name": "Biology", "aliases": ["bio"]},
    "chemistry": {"name": "Chemistry", "aliases": ["chem"]},
    "physics": {"name": "Physics", "aliases": ["phy"]},
    "computer_science": {"name": "Computer Science", "aliases": ["computer", "cs", "computer science and entrepreneurship"]},
    "mathematics": {"name": "Mathematics", "aliases": ["maths", "math"]},
}
SUBJECT_ORDER = list(SUBJECTS)
NUMBERED = re.compile(r"^\d+(\.\d+)+[A-Za-z]?$")


def sid(*parts: object) -> str:
    return str(uuid.uuid5(NAMESPACE, "/".join(str(p) for p in parts)))


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "untitled"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def clean_title(t: str) -> str:
    t = re.sub(r"\s*\((unnumbered|descriptive)[^)]*\)\s*", " ", t, flags=re.I)
    return re.sub(r"\s+", " ", t).strip()


def topic_key(t: dict, seen: dict[str, int]) -> tuple[str, str | None]:
    """Natural-key fragment for a topic, plus the printed heading number (if any)."""
    raw = str(t.get("id") or "").strip()
    # A heading the index marks "(unnumbered)" never displays a number, even if a synthetic id like "13.0" was used.
    unnumbered = "unnumbered" in str(t.get("title", "")).lower()
    number = raw if NUMBERED.match(raw) and not unnumbered else None
    base = number if number else "u-" + slug(clean_title(str(t.get("title", ""))))
    seen[base] = seen.get(base, 0) + 1
    return (base if seen[base] == 1 else f"{base}~{seen[base]}"), number


def build_topics(topics: list, parent_key: str, depth: int, seen: dict[str, int]) -> list[dict]:
    out = []
    for t in topics or []:
        if not isinstance(t, dict):
            continue  # plain-text topic phrases stay in the book index; they are not navigable topics
        frag, number = topic_key(t, seen)
        key = f"{parent_key}/{frag}"
        points = [s for s in (t.get("subtopics") or []) if isinstance(s, str)]
        out.append({
            "id": sid(key),
            "natural_key": key,
            "number": number,
            "title": clean_title(str(t.get("title", ""))),
            "depth": depth,
            "pdf_page": t.get("pdf_page") if isinstance(t.get("pdf_page"), int) else None,
            "points": points,
            "children": build_topics([s for s in (t.get("subtopics") or []) if isinstance(s, dict)], parent_key, depth + 1, seen),
        })
    return out


def count_assessment(ch: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    for a in ch.get("assessment") or []:
        c = a.get("count")
        if isinstance(c, (int, float)):
            out[a.get("type") or "Other"] = out.get(a.get("type") or "Other", 0) + int(c)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="only verify local PDFs against the committed registry")
    args = ap.parse_args()

    if args.check:
        reg = json.loads(OUT_REGISTRY.read_text(encoding="utf-8"))
        bad = 0
        for s in reg["sources"]:
            p = PROJ / s["file"]
            if not p.exists():
                print(f"MISSING  {s['source_id']}: {s['file']}")
                bad += 1
            elif sha256(p) != s["sha256"]:
                print(f"CHANGED  {s['source_id']}: {s['file']} (re-index required)")
                bad += 1
            else:
                print(f"OK       {s['source_id']}")
        return 1 if bad else 0

    old = {}
    if OUT_REGISTRY.exists():
        old = {s["source_id"]: s for s in json.loads(OUT_REGISTRY.read_text(encoding="utf-8"))["sources"]}

    books = []
    for fn in sorted(INDEXES.glob("class_*/*/*_book.json")):
        b = json.loads(fn.read_text(encoding="utf-8"))
        cls = int(b["class"])
        subj = fn.parent.name
        if subj not in SUBJECTS or fn.parent.parent.name != f"class_{cls}":
            raise SystemExit(f"index placement mismatch: {fn}")
        b["_subject"] = subj
        b["_index_json"] = fn.relative_to(PROJ).as_posix()
        books.append(b)
    books.sort(key=lambda b: (int(b["class"]), SUBJECT_ORDER.index(b["_subject"])))

    sources, cat_books = [], []
    for b in books:
        cls, subj, bid = int(b["class"]), b["_subject"], b["book_id"]
        pdf = PROJ / b["filename"]
        if pdf.exists():
            digest, size = sha256(pdf), pdf.stat().st_size
        elif bid in old:
            digest, size = old[bid]["sha256"], old[bid]["bytes"]  # CI has no PDFs; keep the registered values
        else:
            raise SystemExit(f"{bid}: source PDF not found and no registered checksum: {pdf}")
        comp = b.get("completeness") or {}
        src = {
            "source_id": bid,
            "grade": cls,
            "subject": subj,
            "title": b.get("title"),
            "authority": b.get("authority"),
            "publisher": b.get("publisher"),
            "edition": b.get("edition"),
            "curriculum": b.get("curriculum"),
            "language": b.get("language", "English"),
            "file": b["filename"],
            "sha256": digest,
            "bytes": size,
            "pdf_pages": b["pdf_pages"],
            "file_type": b.get("file_type"),
            "page_rule": b.get("page_rule"),
            "completeness": comp.get("status", "unknown"),
            "missing_pages": comp.get("missing_pages") or [],
            "duplicate_pages": comp.get("duplicate_pages") or [],
            "rights": "Owner-supplied textbook marked 'All rights reserved'. Internal use for indexing/derivation; publication rights for derived material UNVERIFIED (owner to confirm).",
            "book_index": b["_index_json"].replace("_book.json", "_book_index.md"),
            "visual_index": b["_index_json"].replace("_book.json", "_visual_index.md"),
            "index_json": b["_index_json"],
            "text_layer_local": "education_knowledge/" + str(b.get("text_layer", "")).replace("education_knowledge/", ""),
            "status": "ACCEPTED_FOR_INTAKE",
        }
        sources.append(src)

        book_key = f"{REGION}/{GRADES[cls]['code'].lower()}/{subj}/{bid.lower()}"
        chapters = []
        for order, ch in enumerate(b["chapters"], start=1):
            ch_key = f"{book_key}/ch{ch['number']}"
            chapters.append({
                "id": sid(ch_key),
                "natural_key": ch_key,
                "order": order,
                "number": ch["number"],
                "contents_number": ch.get("contents_number"),
                "title": clean_title(ch["title"]),
                "status": ch.get("status") or "complete",
                "printed_start": ch.get("printed_start"),
                "printed_end": ch.get("printed_end"),
                "pdf_start": ch.get("pdf_start"),
                "pdf_end": ch.get("pdf_end"),
                "slo_codes": ch.get("slo_codes"),
                "main_concept": ch.get("main_concept"),
                "key_terms": ch.get("key_terms") or [],
                "visual_count": len(ch.get("visuals") or []),
                "assessment_counts": count_assessment(ch),
                "topics": build_topics(ch.get("topics") or [], ch_key, 1, {}),
            })
        cat_books.append({
            "id": sid(book_key),
            "natural_key": book_key,
            "source_id": bid,
            "grade": cls,
            "subject": subj,
            "title": b.get("title"),
            "chapter_label": "Unit" if subj in ("mathematics",) or (subj == "computer_science" and cls == 11) else "Chapter",
            "chapters": chapters,
        })

    grades = [{"id": sid(REGION, g["code"]), "grade": n, **g} for n, g in GRADES.items()]
    subjects = [{"id": sid(REGION, "subject", k), "code": k, "order": i, **v} for i, (k, v) in enumerate(SUBJECTS.items())]
    catalogue = {
        "schema_version": SCHEMA_VERSION,
        "region": {"code": REGION, "name": "Punjab, Pakistan"},
        "scope_decision": "SCOPE-01",
        "grades": grades,
        "subjects": subjects,
        "books": cat_books,
    }
    registry = {"schema_version": SCHEMA_VERSION, "region": REGION, "scope_decision": "SCOPE-01", "sources": sources}

    OUT_CATALOGUE.parent.mkdir(parents=True, exist_ok=True)
    OUT_REGISTRY.write_text(json.dumps(registry, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    OUT_CATALOGUE.write_text(json.dumps(catalogue, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    ids = [c["id"] for bk in cat_books for c in bk["chapters"]]
    def all_topics(ts):
        for t in ts:
            yield t
            yield from all_topics(t["children"])
    tids = [t["id"] for bk in cat_books for c in bk["chapters"] for t in all_topics(c["topics"])]
    assert len(set(ids)) == len(ids), "duplicate chapter ids"
    assert len(set(tids)) == len(tids), "duplicate topic ids"
    for bk in cat_books:
        print(f"{bk['source_id']:9} grade {bk['grade']} {bk['subject']:16} chapters {len(bk['chapters']):2} "
              f"topics {sum(1 for c in bk['chapters'] for _ in all_topics(c['topics']))}")
    print(f"registry: {len(sources)} sources · catalogue: {len(ids)} chapters, {len(tids)} topics")
    return 0


if __name__ == "__main__":
    sys.exit(main())
