"""Quality-control pass over the Class 11 / Class 12 knowledge base.

Usage (from the project root): python education_knowledge/tools/verify_knowledge_base.py [--append-manifest]

Checks: every PDF in the class folders has exactly one book record in the matching class folder; class/subject
assignment matches folder and JSON; source file exists and page count matches; text layer exists with one block per
PDF page; chapters are ordered, non-overlapping and inside the file; every PDF page is covered by front matter /
chapter / back matter; topics, visuals and assessment pages fall inside their chapter; every chapter has topics,
visuals (unless flagged) and assessment (unless flagged); visual IDs are unique and prefixed with the book id;
assessment types are valid; the three per-book files exist; no cross-class contamination in book JSON ids.
"""
import json, glob, os, re, sys
import pymupdf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJ = os.path.dirname(ROOT)
QTYPES = {"MCQ", "FillBlank", "TrueFalse", "Matching", "Short", "Constructed", "Long", "Numerical", "Exercise",
          "Derivation", "Practical", "DiagramBased", "GraphBased", "TableBased", "Conceptual", "Application", "Project", "Other"}
problems, notes = [], []


def walk(ts):
    for t in ts or []:
        if isinstance(t, str):          # topic phrase listed under a heading
            continue
        yield t
        yield from walk(t.get("subtopics"))


for cls in (11, 12):
    folder = os.path.join(PROJ, f"{cls} Class Data")
    pdfs = sorted(os.path.relpath(p, PROJ).replace("\\", "/") for p in glob.glob(os.path.join(folder, "**", "*"), recursive=True) if os.path.isfile(p))
    recs = {}
    for fn in glob.glob(os.path.join(ROOT, "indexes", f"class_{cls}", "*", "*_book.json")):
        b = json.load(open(fn, encoding="utf-8"))
        recs[b["book_id"]] = (b, fn)
    indexed = {b.get("filename", "").replace("\\", "/"): bid for bid, (b, fn) in recs.items()}
    for p in pdfs:
        if p not in indexed:
            problems.append(f"class {cls}: UNINDEXED FILE {p}")
    for f_, bid in indexed.items():
        if f_ not in pdfs:
            problems.append(f"{bid}: filename '{f_}' not found in {cls} Class Data")
    notes.append(f"class {cls}: {len(pdfs)} files in folder, {len(recs)} book records")
    for bid, (b, fn) in recs.items():
        d = os.path.dirname(fn)
        slug = b.get("book_slug") or os.path.basename(fn)[:-10]
        for suffix in ("_book_index.md", "_visual_index.md"):
            if not os.path.exists(os.path.join(d, slug + suffix)):
                problems.append(f"{bid}: missing {slug}{suffix}")
        if int(b.get("class", 0)) != cls or not bid.startswith(f"C{cls}-"):
            problems.append(f"{bid}: class field/id does not match folder class_{cls}")
        if not b.get("filename", "").startswith(f"{cls} Class Data/"):
            problems.append(f"{bid}: filename '{b.get('filename')}' is not inside '{cls} Class Data/' (class contamination)")
        subj = os.path.basename(d)
        if b.get("subject_folder") and b["subject_folder"] != subj:
            problems.append(f"{bid}: subject_folder {b['subject_folder']} != folder {subj}")
        src = os.path.join(PROJ, b.get("filename", ""))
        if not os.path.exists(src):
            continue
        n = pymupdf.open(src).page_count
        if n != b.get("pdf_pages"):
            problems.append(f"{bid}: pdf_pages {b.get('pdf_pages')} != actual {n}")
        tl = os.path.join(ROOT, b.get("text_layer", "").replace("education_knowledge/", ""))
        if not os.path.exists(tl):
            problems.append(f"{bid}: text layer missing {b.get('text_layer')}")
        else:
            k = len(re.findall(r"^=====PAGE \d+=====$", open(tl, encoding="utf-8").read(), re.M))
            if k != n:
                problems.append(f"{bid}: text layer has {k} page blocks, PDF has {n}")
        covered, prev, vids = set(), None, set()
        for ch in b.get("chapters", []):
            st = (ch.get("status") or "complete").lower()
            a, z = ch.get("pdf_start"), ch.get("pdf_end")
            if st == "missing":
                continue
            if not (isinstance(a, int) and isinstance(z, int) and 1 <= a <= z <= n):
                problems.append(f"{bid} Ch{ch.get('number')}: bad PDF range {a}-{z}")
                continue
            if prev and a <= prev[1]:
                problems.append(f"{bid} Ch{ch.get('number')}: overlaps Ch{prev[0]} (starts {a} <= {prev[1]})")
            prev = (ch.get("number"), z)
            covered |= set(range(a, z + 1))
            if not ch.get("topics"):
                problems.append(f"{bid} Ch{ch.get('number')}: no topics")
            for t in walk(ch.get("topics")):
                p = t.get("pdf_page")
                if isinstance(p, int) and not (a <= p <= z):
                    problems.append(f"{bid} Ch{ch.get('number')}: topic {t.get('id')} '{str(t.get('title'))[:40]}' page {p} outside {a}-{z}")
            vs = ch.get("visuals") or []
            if not vs and "no visuals" not in " ".join(ch.get("issues") or []).lower():
                notes.append(f"{bid} Ch{ch.get('number')}: no visuals recorded")
            for v in vs:
                vid = v.get("visual_id", "")
                if not vid.startswith(bid + "/"):
                    problems.append(f"{bid} Ch{ch.get('number')}: visual id '{vid}' not prefixed with book id")
                if vid in vids:
                    problems.append(f"{bid}: duplicate visual id {vid}")
                vids.add(vid)
                p = v.get("pdf_page")
                if isinstance(p, int) and not (a <= p <= z):
                    problems.append(f"{bid} Ch{ch.get('number')}: visual {vid} page {p} outside {a}-{z}")
            asm = ch.get("assessment") or []
            if not asm and st == "complete":
                notes.append(f"{bid} Ch{ch.get('number')}: no assessment sections recorded")
            for s_ in asm:
                if s_.get("type") not in QTYPES:
                    problems.append(f"{bid} Ch{ch.get('number')}: invalid assessment type '{s_.get('type')}' in '{s_.get('section')}'")
                for p in s_.get("pdf_pages") or []:
                    if isinstance(p, int) and not (a <= p <= z):
                        problems.append(f"{bid} Ch{ch.get('number')}: assessment '{s_.get('section')}' page {p} outside {a}-{z}")
        for m in b.get("back_matter") or []:
            a, z = m.get("pdf_start"), m.get("pdf_end")
            if isinstance(a, int) and isinstance(z, int):
                covered |= set(range(a, z + 1))
        first = min(covered) if covered else 1
        unc = [p for p in range(first, n + 1) if p not in covered]
        notes.append(f"{bid}: {len(b.get('chapters', []))} chapters, front matter PDF 1-{first - 1}, uncovered pages: {unc or 'none'}")
        if unc:
            problems.append(f"{bid}: PDF pages not assigned to any chapter/back matter: {unc}")

print("=== NOTES ===")
for x in notes:
    print(" ", x)
print("=== PROBLEMS ===")
for x in problems:
    print(" ", x)
if not problems:
    print("  none")
if "--append-manifest" in sys.argv:
    import datetime
    mf = os.path.join(ROOT, "Academic_Library_Index_Manifest.md")
    with open(mf, "a", encoding="utf-8") as f:
        f.write(f"\n### Validation run {datetime.date.today().isoformat()}\n\n")
        f.write(f"- Result: **{'PASS' if not problems else 'FAIL'}** — {len(problems)} problems, {len(notes)} notes\n")
        for x in problems:
            f.write(f"- PROBLEM: {x}\n")
        for x in notes:
            f.write(f"- note: {x}\n")
sys.exit(1 if problems else 0)
