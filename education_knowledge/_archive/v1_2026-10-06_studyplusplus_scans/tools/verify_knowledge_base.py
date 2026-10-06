"""Completeness / consistency checks for the education knowledge base.

Usage (from project root): python education_knowledge/tools/verify_knowledge_base.py
Checks: every PDF in the class folders is indexed; book class matches its folder; chapter page ranges are
inside the file, ordered and non-overlapping (documented exceptions allowed); every PDF page is accounted
for (front matter / chapter / back matter); topic pages fall inside their chapter; OCR layer exists and
has one block per PDF page; source PDFs exist and page counts match.
"""
import json, glob, os, re, sys
import pymupdf

PROJ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KB = os.path.join(PROJ, "education_knowledge")
ALLOWED_OVERLAP = {("C11-CHEM", 6, 7)}   # printed pp.125-140 scanned twice; Ch7 opener at PDF 158 & 160
problems, notes = [], []


def walk(ts):
    for t in ts or []:
        yield t
        yield from walk(t.get("subtopics"))


books = {}
for fn in sorted(glob.glob(os.path.join(KB, "books", "*.json"))):
    b = json.load(open(fn, encoding="utf-8"))
    books[b["book_id"]] = b

# 1. every PDF in the dataset folders is indexed exactly once
pdfs = sorted(glob.glob(os.path.join(PROJ, "1? Class Data", "**", "*"), recursive=True))
pdfs = [os.path.relpath(p, PROJ).replace("\\", "/") for p in pdfs if os.path.isfile(p)]
indexed = {b["source_pdf"]: bid for bid, b in books.items()}
for p in pdfs:
    if p not in indexed:
        problems.append(f"UNINDEXED FILE: {p}")
notes.append(f"{len(pdfs)} files in dataset folders; {len(indexed)} indexed")

for bid, b in books.items():
    src = os.path.join(PROJ, b["source_pdf"])
    # 2. class separation
    folder_cls = int(b["source_pdf"][:2])
    if folder_cls != int(b["class"]) or not bid.startswith(f"C{folder_cls}-"):
        problems.append(f"{bid}: class mismatch with folder {b['source_pdf']}")
    # 3. file exists, page count
    if not os.path.exists(src):
        problems.append(f"{bid}: source missing {src}"); continue
    n = pymupdf.open(src).page_count
    if n != b.get("pdf_pages"):
        problems.append(f"{bid}: pdf_pages {b.get('pdf_pages')} != actual {n}")
    # 4. OCR layer
    ocr = os.path.join(KB, "source_text", f"{bid}.ocr.txt")
    if not os.path.exists(ocr):
        problems.append(f"{bid}: OCR layer missing")
    else:
        k = len(re.findall(r"^=====PAGE \d+=====$", open(ocr, encoding="utf-8").read(), re.M))
        if k != n:
            problems.append(f"{bid}: OCR layer has {k} pages, PDF has {n}")
    # 5. chapter ranges
    chs = b["chapters"]
    covered = set()
    prev = None
    for ch in chs:
        a, z = ch.get("pdf_start"), ch.get("pdf_end")
        st = (ch.get("status") or "complete").lower()
        if st == "missing":
            continue
        if not (isinstance(a, int) and isinstance(z, int) and 1 <= a <= z <= n):
            problems.append(f"{bid} Ch{ch['number']}: bad PDF range {a}-{z}"); continue
        if prev and a <= prev[1] and (bid, prev[0], ch["number"]) not in ALLOWED_OVERLAP:
            problems.append(f"{bid} Ch{ch['number']}: overlaps previous chapter ({prev[1]} >= {a})")
        prev = (ch["number"], z)
        covered |= set(range(a, z + 1))
        if not ch.get("topics"):
            problems.append(f"{bid} Ch{ch['number']}: no topics recorded")
        for t in walk(ch.get("topics")):
            p = t.get("pdf_page")
            if isinstance(p, int) and not (a <= p <= z):
                problems.append(f"{bid} Ch{ch['number']}: topic {t.get('id')} '{t.get('title','')[:40]}' page {p} outside {a}-{z}")
        ex = (ch.get("exercise") or {}).get("sections")
        if not ex:
            notes.append(f"{bid} Ch{ch['number']}: no exercise sections recorded (status {st})")
    for m in b.get("back_matter") or []:
        a, z = m.get("pdf_start"), m.get("pdf_end")
        if isinstance(a, int) and isinstance(z, int):
            covered |= set(range(a, z + 1))
    first = min(covered) if covered else 1
    uncovered = [p for p in range(first, n + 1) if p not in covered]
    notes.append(f"{bid}: {len(chs)} chapters; front matter PDF 1-{first-1}; pages not in any chapter/back-matter range: {uncovered or 'none'}")

print("=== NOTES ==="); [print(" ", x) for x in notes]
print("=== PROBLEMS ==="); [print(" ", x) for x in problems] if problems else print("  none")
sys.exit(1 if problems else 0)
