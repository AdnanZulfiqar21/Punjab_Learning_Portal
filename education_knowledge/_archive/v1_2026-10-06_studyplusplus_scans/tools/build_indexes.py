"""Rebuild the generated master indexes from the per-book JSON files.

Usage (from the project root):
    python education_knowledge/tools/build_indexes.py

Inputs : education_knowledge/books/<BOOK_ID>.json   (one per textbook; hand-curated)
Outputs: education_knowledge/CLASS_11_MASTER_INDEX.md
         education_knowledge/CLASS_12_MASTER_INDEX.md
         education_knowledge/CHAPTER_TOPIC_INDEX.md
         education_knowledge/SOURCE_FILE_MAP.md
         education_knowledge/QUESTION_INVENTORY.md
         education_knowledge/knowledge_map.json
BOOK_CATALOG.md, SUBJECT_INDEX.md, EDUCATION_DATA_ROADMAP.md and README.md are written by hand.
Edit the per-book JSON (and books/<ID>.md), then re-run this script. Never edit generated files directly.
"""
import json, glob, os, re, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOKS = os.path.join(ROOT, "books")
SUBJECT_ORDER = ["Physics", "Chemistry", "Biology", "Mathematics", "Computer Science"]
GEN_NOTE = ("> **Generated file** — produced by `tools/build_indexes.py` from `books/*.json` on {date}. "
            "Do not edit by hand; fix the per-book JSON and re-run.\n")


def load_books():
    books = []
    for fn in sorted(glob.glob(os.path.join(BOOKS, "*.json"))):
        with open(fn, encoding="utf-8") as f:
            b = json.load(f)
        b["_file"] = os.path.basename(fn)
        books.append(b)
    def key(b):
        subj = b.get("subject", "")
        idx = next((i for i, s in enumerate(SUBJECT_ORDER) if s.lower() in subj.lower()), 99)
        return (int(b.get("class", 0)), idx, b.get("book_id", ""))
    return sorted(books, key=key)


def subject_key(b):
    s = b.get("subject", "")
    for name in SUBJECT_ORDER:
        if name.lower() in s.lower():
            return name
    return s


def pg(v):
    return "?" if v in (None, "", 0) else str(v)


def rng(a, b):
    if a in (None, "", 0) and b in (None, "", 0):
        return "—"
    return f"{pg(a)}–{pg(b)}"


def status_of(ch):
    s = (ch.get("status") or "complete").lower()
    return "" if s == "complete" else f" **[{s.upper()}]**"


SKIP = re.compile(r"answer key|summary|glossary|key points", re.I)  # not question sections
QTYPES = [
    ("Other", re.compile(r"activity|project|inquisitive", re.I)),
    ("MCQ", re.compile(r"multiple|mcq|choice", re.I)),
    ("Short", re.compile(r"short|brief|quick", re.I)),
    ("Constructed", re.compile(r"constructed", re.I)),
    ("Long", re.compile(r"long|descriptive|extended|essay|detail|comprehensive", re.I)),
    ("Numerical", re.compile(r"numerical|problem|exercise\s*\d|review exercise|calculation|exercise", re.I)),
]
BUCKETS = ["MCQ", "Short", "Constructed", "Long", "Numerical", "Other"]


def classify(name):
    if SKIP.search(name or ""):
        return None
    for label, rx in QTYPES:
        if rx.search(name or ""):
            return label
    return "Other"


def qcounts(ch):
    out = {k: 0 for k in BUCKETS}
    ex = ch.get("exercise") or {}
    for s in ex.get("sections") or []:
        c, kind = s.get("count"), classify(s.get("name"))
        if kind and isinstance(c, (int, float)):
            out[kind] += int(c)
    return out


def tid_of(t):
    """Numbered heading id, or None for un-numbered headings (some books store 'unnumbered')."""
    i = t.get("id")
    return i if i and re.search(r"\d", str(i)) else None


def walk(topics, depth=0):
    for t in topics or []:
        yield depth, t
        yield from walk(t.get("subtopics"), depth + 1)


def topic_line(t, depth):
    tid = tid_of(t)
    label = f"{tid} {t.get('title','')}" if tid else f"{t.get('title','')} *(unnumbered)*"
    p = t.get("pdf_page")
    return "  " * depth + f"- {label}" + (f" — PDF p.{p}" if p else "")


def write(name, text):
    with open(os.path.join(ROOT, name), "w", encoding="utf-8") as f:
        f.write(text)
    print("wrote", name)


def build_class_index(books, cls, date):
    L = [f"# Class {cls} — Master Index\n", GEN_NOTE.format(date=date)]
    L.append(f"Hierarchy: **Class {cls} → Subject → Book → Chapter → Topic (→ Subtopic)**. "
             "Page numbers are **PDF page indices** of the source file unless marked *printed*. "
             "Full sub-topic depth is in `CHAPTER_TOPIC_INDEX.md`; deep chapter notes (concepts, terms, formulas, exercises) "
             "are in `books/<BOOK_ID>.md`.\n")
    cb = [b for b in books if int(b.get("class", 0)) == cls]
    L.append("## Contents\n")
    for b in cb:
        L.append(f"- [{subject_key(b)} — {b['book_id']}](#{b['book_id'].lower()}) · {len(b.get('chapters', []))} chapters")
    L.append("")
    for b in cb:
        L.append(f"## {subject_key(b)} — {b['book_id']}\n<a id=\"{b['book_id'].lower()}\"></a>\n")
        L.append(f"- **Book:** {b.get('title','')}  ")
        L.append(f"- **Authority / curriculum:** {b.get('authority','')} · {b.get('curriculum','')}  ")
        L.append(f"- **Edition:** {b.get('edition','')}  ")
        L.append(f"- **Source file:** `{b.get('source_pdf','')}` ({b.get('pdf_pages','?')} PDF pages) · page rule: {b.get('page_offset_rule','')}  ")
        L.append(f"- **Text layer:** `source_text/{b['book_id']}.ocr.txt` · **Deep notes:** `books/{b['book_id']}.md`\n")
        L.append("| Ch | Title | Printed pp. | PDF pp. | Topics | Status |")
        L.append("|---|---|---|---|---|---|")
        for ch in b.get("chapters", []):
            n_top = sum(1 for d, t in walk(ch.get("topics")) if d == 0 and tid_of(t))
            L.append(f"| {ch.get('number')} | {ch.get('title')} | {rng(ch.get('printed_start'), ch.get('printed_end'))} | "
                     f"{rng(ch.get('pdf_start'), ch.get('pdf_end'))} | {n_top} | {(ch.get('status') or 'complete')} |")
        L.append("")
        for ch in b.get("chapters", []):
            L.append(f"### {b['book_id']} · Ch {ch.get('number')} — {ch.get('title')}{status_of(ch)}")
            L.append(f"PDF pp. {rng(ch.get('pdf_start'), ch.get('pdf_end'))} (printed {rng(ch.get('printed_start'), ch.get('printed_end'))})"
                     + (f" · SLOs {ch['slo_codes']}" if ch.get("slo_codes") and "not printed" not in str(ch.get("slo_codes")).lower() else ""))
            if ch.get("main_concept"):
                L.append(f"\n*{ch['main_concept']}*\n")
            for d, t in walk(ch.get("topics")):
                if d <= 1:
                    L.append(topic_line(t, d))
            L.append("")
        if b.get("back_matter"):
            L.append(f"**Back matter / supplementary ({b['book_id']}):**\n")
            for m in b["back_matter"]:
                L.append(f"- {m.get('name')} — PDF pp. {rng(m.get('pdf_start'), m.get('pdf_end'))}" + (f": {m['description']}" if m.get("description") else ""))
            L.append("")
    return "\n".join(L) + "\n"


def build_chapter_topic(books, date):
    L = ["# Chapter → Topic → Subtopic Index (all books, full depth)\n", GEN_NOTE.format(date=date)]
    L.append("Lookup key format: `C<class>-<SUBJ> / Ch <n> / <topic id>`. Page numbers are PDF page indices.\n")
    for cls in (11, 12):
        L.append(f"# Class {cls}\n")
        for b in [x for x in books if int(x.get("class", 0)) == cls]:
            L.append(f"## {b['book_id']} — {subject_key(b)} (`{b.get('source_pdf','')}`)\n")
            for ch in b.get("chapters", []):
                L.append(f"### {b['book_id']} / Ch {ch.get('number')} — {ch.get('title')}{status_of(ch)} · PDF {rng(ch.get('pdf_start'), ch.get('pdf_end'))}")
                any_t = False
                for d, t in walk(ch.get("topics")):
                    L.append(topic_line(t, d)); any_t = True
                if not any_t:
                    L.append("- *(no topics available — see status/notes)*")
                if ch.get("key_terms"):
                    L.append(f"\n**Key terms:** {', '.join(ch['key_terms'])}")
                if ch.get("formulas") and ch["formulas"] not in (["None"], ["none"]):
                    L.append(f"\n**Formulas / laws:** " + "; ".join(ch["formulas"]))
                L.append("")
    return "\n".join(L) + "\n"


def build_source_map(books, date):
    L = ["# Source File Map\n", GEN_NOTE.format(date=date)]
    L.append("Every indexed chapter maps to a page range in an original file. Original files are **read-only**; "
             "the OCR text layer for each file lives in `source_text/`.\n")
    L.append("| Book ID | Class | Subject | Source file | PDF pages | Page rule | OCR text layer |")
    L.append("|---|---|---|---|---|---|---|")
    for b in books:
        L.append(f"| {b['book_id']} | {b.get('class')} | {subject_key(b)} | `{b.get('source_pdf')}` | {b.get('pdf_pages')} | "
                 f"{b.get('page_offset_rule','')} | `source_text/{b['book_id']}.ocr.txt` |")
    L.append("")
    for b in books:
        L.append(f"## `{b.get('source_pdf')}` → {b['book_id']}\n")
        L.append("| Section | Printed pp. | PDF pp. | Exercise PDF pp. | Status |")
        L.append("|---|---|---|---|---|")
        for ch in b.get("chapters", []):
            ex = (ch.get("exercise") or {}).get("pdf_pages") or []
            exs = rng(ex[0], ex[-1]) if ex else "—"
            L.append(f"| Ch {ch.get('number')} {ch.get('title')} | {rng(ch.get('printed_start'), ch.get('printed_end'))} | "
                     f"{rng(ch.get('pdf_start'), ch.get('pdf_end'))} | {exs} | {ch.get('status') or 'complete'} |")
        for m in b.get("back_matter") or []:
            L.append(f"| {m.get('name')} | — | {rng(m.get('pdf_start'), m.get('pdf_end'))} | — | back matter |")
        if b.get("issues"):
            L.append("\n**File issues:**\n")
            for i in b["issues"]:
                L.append(f"- {i}")
        L.append("")
    return "\n".join(L) + "\n"


def build_questions(books, date):
    L = ["# Question Inventory (textbook end-of-chapter material)\n", GEN_NOTE.format(date=date)]
    L.append("Counts come from the end-of-chapter exercise sections recorded in `books/*.json` and are bucketed automatically "
             "by section name (MCQ / Short / Constructed-response / Long = long, descriptive, comprehensive, extended / Numerical = numerical problems and maths exercise questions / Other = inquisitive questions, activities). "
             "Exact section names and per-section counts are in `books/<BOOK_ID>.md` §4 and §6. "
             "These are **textbook exercises only**; the dataset contains no separate question banks, past papers or answer keys "
             "beyond what is printed inside the books.\n")
    grand = {k: 0 for k in BUCKETS}
    for cls in (11, 12):
        L.append(f"## Class {cls}\n")
        for b in [x for x in books if int(x.get("class", 0)) == cls]:
            L.append(f"### {b['book_id']} — {subject_key(b)}\n")
            L.append("| Ch | Title | MCQ | Short | Constructed | Long | Numerical / exercise Qs | Other | Exercise PDF pp. | Answers |")
            L.append("|---|---|---|---|---|---|---|---|---|---|")
            tot = {k: 0 for k in BUCKETS}
            for ch in b.get("chapters", []):
                q = qcounts(ch)
                for k in tot: tot[k] += q[k]
                ex = (ch.get("exercise") or {}).get("pdf_pages") or []
                L.append(f"| {ch.get('number')} | {ch.get('title')}{status_of(ch)} | {q['MCQ']} | {q['Short']} | {q['Constructed']} | {q['Long']} | {q['Numerical']} | {q['Other']} | "
                         f"{rng(ex[0], ex[-1]) if ex else '—'} | {str(ch.get('answers_available','?'))[:60]} |")
            L.append("| **Total** | | " + " | ".join(f"**{tot[k]}**" for k in BUCKETS) + " | | |\n")
            for k in grand: grand[k] += tot[k]
    L.append("**All books:** " + " · ".join(f"{k} {grand[k]}" for k in BUCKETS) + "\n")
    return "\n".join(L) + "\n"


def main():
    date = datetime.date.today().isoformat()
    books = load_books()
    write("CLASS_11_MASTER_INDEX.md", build_class_index(books, 11, date))
    write("CLASS_12_MASTER_INDEX.md", build_class_index(books, 12, date))
    write("CHAPTER_TOPIC_INDEX.md", build_chapter_topic(books, date))
    write("SOURCE_FILE_MAP.md", build_source_map(books, date))
    write("QUESTION_INVENTORY.md", build_questions(books, date))
    km = {"generated": date, "hierarchy": "class > subject > book > chapter > topic > subtopic",
          "classes": {}}
    for b in books:
        bb = {k: v for k, v in b.items() if not k.startswith("_")}
        km["classes"].setdefault(str(b.get("class")), {}).setdefault(subject_key(b), []).append(bb)
    with open(os.path.join(ROOT, "knowledge_map.json"), "w", encoding="utf-8") as f:
        json.dump(km, f, ensure_ascii=False, indent=1)
    print("wrote knowledge_map.json")
    for b in books:
        n_ch = len(b.get("chapters", []))
        n_t = sum(1 for ch in b.get("chapters", []) for d, t in walk(ch.get("topics")) if tid_of(t))
        print(f"  {b['book_id']}: {n_ch} chapters, {n_t} numbered topics/subtopics")


if __name__ == "__main__":
    main()
