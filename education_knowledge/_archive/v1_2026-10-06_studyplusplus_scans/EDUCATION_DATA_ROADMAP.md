# Education Data Roadmap — Class 11 & Class 12 Knowledge Base

**Built:** 2026-10-06 · **Dataset:** `11 Class Data/` (5 PDFs) and `12 Class Data/` (5 PDFs), all PECTAA NCP-2023 Experimental Edition textbooks · **Status:** analysis complete and verified (§8).

This is the entry point for any future work that needs the textbook content: tests, MCQs, short/long questions, answer checking, chapter selection, syllabus mapping or AI features. Read this first, then follow the links.

---

## 1. Quick lookup recipes

| Question | Where to look |
|---|---|
| Which books exist? Edition, publisher, file status? | `BOOK_CATALOG.md` |
| Which subject / class does a book belong to? How do Class 11 and 12 chapters relate? | `SUBJECT_INDEX.md` |
| What is Chapter X called, and which topics does it have? | `CLASS_11_MASTER_INDEX.md` / `CLASS_12_MASTER_INDEX.md` (2 levels), `CHAPTER_TOPIC_INDEX.md` (full depth, key terms, formulas) |
| What does a chapter teach: concepts, SLOs, definitions, examples, exercises, quirks? | `books/<BOOK_ID>.md` §4 |
| Which file and page contains topic Y? | `CHAPTER_TOPIC_INDEX.md` (PDF page per heading) → `SOURCE_FILE_MAP.md` (file + page rule) |
| Original wording of a page (searchable) | `source_text/<BOOK_ID>.ocr.txt`, search `=====PAGE n=====`. Verify formulas and tables against the PDF image. |
| How many MCQ/short/long/numerical questions per chapter? Are answers available? | `QUESTION_INVENTORY.md`, then `books/<BOOK_ID>.md` §6 |
| Exam paper structure (marks, time, chapter allocation) | `EXAM_BLUEPRINTS.md` (Class 12 only) |
| Programmatic access | `knowledge_map.json` (all books) or `books/<BOOK_ID>.json` (one book) |

**Example:** *"Give me Class 11 Physics Chapter 4 questions"*: go to `books/C11-PHY.md` → "Chapter 4 — Work, Energy and Power" → End-of-chapter assessment (section names, counts, PDF pages). Read those PDF pages in `source_text/C11-PHY.ocr.txt`, or render them from `11 Class Data/11 Physics Book Punjab Board.pdf`.

**Example:** *"Which topics belong to Class 12 Biology Chapter 7?"*: Class 12 Biology numbering **continues** from Class 11, so it starts at Chapter 13 and **there is no Chapter 7 in Class 12**. Chapter 7 is Class 11 (`C11-BIO` Ch 7, Structural and Computational Biology). Always confirm the class and book ID before answering. See `SUBJECT_INDEX.md`.

---

## 2. Dataset at a glance

| | Class 11 | Class 12 |
|---|---|---|
| Subjects | 5: Physics, Chemistry, Biology, Mathematics, Computer Science | 5: same |
| Books (= files) | 5 | 5 |
| PDF pages | 1,324 | 1,164 |
| Chapters indexed | **63** (PHY 12, CHEM 16, BIO 12, MATH 14, CS 9) | **59** (PHY 9, CHEM 17, BIO 13, MATH 11, CS 9) |
| Numbered topics + subtopics | 1,073 | 723 |
| End-of-chapter MCQs | 507 | 474 |
| Short questions | 500 | 422 |
| Constructed-response | 81 | 118 |
| Long / descriptive / comprehensive | 307 | 301 |
| Numerical problems + maths exercise questions | 542 | 491 |
| Other (inquisitive questions, activities) | 53 | 50 |
| Pairing scheme / model paper | none | all 5 books |

Chapter numbering: Physics, Chemistry and Biology **continue** into Class 12 (PHY 13–21, CHEM 17–33, BIO 13–25). Mathematics and Computer Science **restart at 1**.

---

## 3. Data model and conventions

```
Class (11 | 12)
 └─ Subject (Physics | Chemistry | Biology | Mathematics | Computer Science)
     └─ Book  (BOOK_ID = C<class>-<PHY|CHEM|BIO|MATH|CS>; 1 book = 1 source PDF)
         └─ Chapter / Unit (number as printed; status complete | partial | missing)
             └─ Topic (N.n, as printed) → Subtopic (N.n.n …) ; un-numbered headings have id = null
                 └─ Question source: end-of-chapter section (MCQ | Short | Constructed | Long | Numerical | Other)
                     └─ Source: file + PDF page (+ printed page via the book's page rule)
```

- **Two page systems.** *PDF page* = 1-based index in the file, used everywhere unless stated otherwise. *Printed page* = number printed on the page. Each book's rule (`page_offset_rule`) converts between them. Most books use a constant offset (+2, +3 or +4). C11-CHEM and C11-MATH have piecewise rules (§6).
- **Chapter keys:** `<BOOK_ID>/Ch<n>`, e.g. `C11-PHY/Ch4`, `C12-CHEM/Ch27`. Topic keys: `<BOOK_ID>/Ch<n>/<topic id>`, e.g. `C12-BIO/Ch13/13.1.2`.
- Headings were recorded as printed. Obvious OCR spelling errors were fixed and nothing was invented. Where the book's own numbering skips or repeats, it was kept as printed and noted.
- Summaries, key-term lists and formulas in `books/*.md` are **index metadata in our own words**, not reproductions of the textbook. The original text stays in the PDFs and OCR layer.

---

## 4. Folder structure (`education_knowledge/`)

| Path | Kind | Purpose |
|---|---|---|
| `README.md` | hand | Short orientation |
| `EDUCATION_DATA_ROADMAP.md` | hand | This file |
| `BOOK_CATALOG.md` | hand | Book metadata, material classification, file status |
| `SUBJECT_INDEX.md` | hand | Subject view, Class 11 ↔ 12 continuity and cross-links |
| `EXAM_BLUEPRINTS.md` | hand | Class 12 pairing schemes / paper patterns / model papers |
| `CLASS_11_MASTER_INDEX.md`, `CLASS_12_MASTER_INDEX.md` | generated | Per-class Subject → Book → Chapter → Topic → Subtopic, with pages |
| `CHAPTER_TOPIC_INDEX.md` | generated | Full-depth topic tree for every chapter, key terms, formulas |
| `SOURCE_FILE_MAP.md` | generated | File → chapter/back-matter page ranges, page rules, file issues |
| `QUESTION_INVENTORY.md` | generated | Question counts per chapter by type, answer availability |
| `knowledge_map.json` | generated | All book JSON merged under class → subject |
| `books/<BOOK_ID>.md` | curated | **Deep per-book analysis**: metadata, page integrity, TOC, per-chapter concept / SLOs / topic tree / terms / formulas / examples / exercises / cross-links / issues, back matter, question inventory |
| `books/<BOOK_ID>.json` | curated | Machine-readable form of the same (source of truth for generated files) |
| `source_text/<BOOK_ID>.ocr.txt` | derived | Full OCR text, page-marked by PDF page (4.2 MB) |
| `tools/ocr_pdf.py` | tool | Re-OCR a PDF (Windows built-in OCR) |
| `tools/render_pages.py` | tool | Render PDF pages to PNG for visual checking |
| `tools/build_indexes.py` | tool | Regenerate generated files from `books/*.json` |
| `tools/verify_knowledge_base.py` | tool | Completeness / consistency checks (§8) |

---

## 5. How the knowledge base was built

1. **Inventory.** Both folders were scanned recursively and held exactly 10 files (5 + 5), all PDFs, with no subfolders and no other file types.
2. **Format check.** Every PDF is a scanned image with no text layer (only the "studyplusplus.com (study++)" watermark is extractable). There are no PDF bookmarks or outlines.
3. **OCR.** All 2,488 pages were OCR'd at 200 DPI with Windows.Media.Ocr (`tools/ocr_pdf.py`). 4 pages came back with little or no text (§6.4).
4. **TOC capture.** Every book's printed Table of Contents was read **visually** from the page images (OCR garbles TOC numbers).
5. **Page mapping.** Printed page numbers were matched to PDF pages per book, which exposed the C11-MATH gap and the C11-CHEM duplicates. Both were confirmed visually.
6. **Deep reading.** Each book was read in full (OCR text, chapter by chapter), with page images checked wherever headings, numbering, question counts, formulas, answer keys or pairing schemes were unclear. The output is `books/<ID>.md` and `.json`.
7. **Generation and verification.** Master indexes were generated from the JSON and verified automatically (§8). Hand-written files were cross-checked against the JSON.

---

## 6. Dataset gaps, anomalies and Requires-Review register

### 6.1 Missing content (critical)
| ID | File | Problem | Impact |
|---|---|---|---|
| G1 | C11-MATH · `11 Class Data/11 Mathematics Book Punjab Board.pdf` | **Printed pages 100–149 (50 pages) are absent.** PDF 102 = printed 99 (mid §6.5.2 Properties of G.P.) and PDF 103 = printed 150 (end of Exercise 8.1). | **Unit 6** Sequences & Series is **partial**: everything after §6.5.2 is missing, including Exercises 6.5–6.11. **Unit 7** Permutations & Combinations is **entirely missing**. **Unit 8** is **partial**: §8.1 and most of Exercise 8.1 are missing; §8.2–8.5 are present. The Answers section still has answers for Ex. 6.5–6.11 and 7.1–7.4. **Obtain a complete copy before building Class 11 maths content for these units.** |
| G2 | C12-MATH · `12 Class Data/12 Mathematics Book Punjab Board (Study++).pdf` | The model paper is cut off at the end of PDF 320 (in Q9(b)). The final page appears to be missing. | Model paper incomplete. Textbook content is unaffected. |

### 6.2 Duplicated pages
| ID | File | Problem |
|---|---|---|
| D1 | C11-CHEM | Printed pp.125–140 were each **scanned twice**, giving 16 extra PDF pages (PDF 129–160, interleaved in two-page spreads). Use the first copy as canonical. The exact pair list is in `books/C11-CHEM.md` §2. Page rule: pdf = printed+4 for printed 1–124, and pdf = printed+20 for printed 141–340. No content is missing. Ch 6 = PDF 116–159; Ch 7 opener appears at PDF 158 and 160. |
| D2 | C12-BIO | Not a scan duplicate: the end of the monoclonal-antibody paragraph is printed twice by the publisher (PDF 186–187). |

**No duplicate books, alternative editions, split volumes or teacher/student versions exist.** Similarly named chapters across classes are different content, not duplicates (`SUBJECT_INDEX.md`).

### 6.3 Answer-key availability (affects auto-marking)
| Book | MCQ key | Short/long answers | Numerical answers |
|---|---|---|---|
| C11-PHY, C12-PHY | ❌ none | ❌ | ✅ printed inline after most problems (a few missing or illegible, listed per book) |
| C11-CHEM, C12-CHEM | ❌ none | ❌ | ❌ |
| C11-BIO, C12-BIO | ❌ none | ❌ | n/a |
| C11-MATH, C12-MATH | n/a (no MCQs in the textbook) | — | ✅ Answers sections (C12: Ex 10.1 only Q1–21 of 24, Ex 9.2 only Q20, Ex 3.7 key numbering mismatch; C11: no answers for Ex 8.1) |
| C11-CS | ✅ 77/78 (Unit 5 Q8 missing) | ❌ | n/a |
| C12-CS | ✅ 90/90 (**Ch 9 Q10 printed key is wrong**: keyed C, correct is (b) GDPR) | ❌ | n/a |

The physics MCQ options that OCR destroyed (symbol-only options) are listed in `books/C11-PHY.md` and `books/C12-PHY.md` §7. They must be transcribed from the page images.

### 6.4 Pages with little or no OCR text (not unreadable, just image-based)
- C11-CS PDF 144: MCQ answer grid. Read visually and recorded in `books/C11-CS.json`.
- C11-MATH PDF 248–249: answer pages made up mostly of graphs.
- C12-CHEM PDF 4: Periodic Table image.

No page in any file is blank, corrupt or out of order.

### 6.5 OCR limitations (all books)
Prose OCR is good. **Equations, chemical formulas and structures, matrices, tables, code listings and diagram labels are often garbled.** Formulas listed in `books/*.md` were rebuilt from page images and context and spot-checked, so verify them against the PDF before quoting. Never generate an answer key from OCR'd maths or chemistry without checking the image.

### 6.6 Textbook-internal inconsistencies (Requires Review — the book itself, not our index)
- **C11-BIO Ch 4:** the TOC says "Molecular Biology", the chapter opener says "Biomolecules" (PDF 94). Indexed under the TOC title, with the alias noted.
- **Numbering slips, recorded as printed:**
  - C11-BIO: animal phyla list skips 9.
  - C11-CHEM: "13.1" printed twice, "10.22.2" inside 10.21, Sample Problem 6.6 used twice.
  - C11-CS: 2.4.1.3 used twice, 5.5.2 printed as "5.2.2", 9.4.3 missing.
  - C11-MATH: 1.4 and 1.4.1 repeated.
  - C12-BIO: 23.4.1 missing.
  - C12-CHEM: SLO code ranges out of order.
  - C11-CHEM: SLO ranges repeat across chapters 2, 3, 4 and 7.
- **Questions or SLOs not covered by the chapter text** (risky as test items without teacher review): examples in C11-BIO (genetic drift, lung volumes, bone repair), C11-CS (Blockchain 2.0, Boolean operators), C11-CHEM Ch 16 (chromyl-chloride and brown-ring tests), C12-BIO Ch 25 (tropical rain forest), C12-CS (rule-based learning), C12-PHY Ch 20 (no numericals, but the paper expects one). Full lists are in each `books/<ID>.md` §7.
- **Probable printing errors:**
  - C11-BIO: "Berzelius 1938"; myoglobin called a "polynucleotide".
  - C11-PHY: printed answers 2.5, 5.6 and 7.9 look wrong.
  - C11-CHEM: conflicting electron-affinity values.
  - C12-CHEM: cell-potential mismatch on PDF 34.
  - C12-BIO: Phase 3 trial size; error-bar limit.
  - C12-CS: F1 value 0.8880.
- **Dated content:** C12-BIO Ch 25 cites 2025–2026 figures (floods, CO₂ 428 ppm).

### 6.7 Coverage gaps relative to the project roadmap
- **Subjects absent:** English, Statistics, Logical Reasoning, and the compulsory subjects (Urdu, Islamiat, Pakistan Studies, Tarjuma-tul-Quran). The roadmap's ECAT/MDCAT profiles need English (and Statistics for some ECAT combinations).
- **No Class 11 exam blueprint** (pairing scheme / model paper) in the dataset.
- **No past board papers, question banks, MCQ banks, solution manuals or notes.** All question material is textbook end-of-chapter exercises (plus the Class 12 model papers).
- **Mathematics has no MCQs** in either textbook, but the C12-MATH paper pattern needs 20 MCQs. Maths MCQs must be authored.
- **Experimental-edition caveat:** all books are 1st-impression experimental editions. Content, numbering and page numbers may change in later printings, so store the edition with every content record (roadmap §3.2).

---

## 7. Readiness for test generation

| Test type | Supported now from the dataset | Notes |
|---|---|---|
| Chapter-wise MCQ test | PHY, CHEM, BIO, CS (both classes) | 981 textbook MCQs. Keys exist only for CS, so other keys must be authored and reviewed. |
| Short-question test | PHY, CHEM, BIO, CS | 922 short items; no model answers in the books. |
| Long-question test | PHY, CHEM, BIO, CS | 608 long + 199 constructed-response. |
| Numerical / problem test | PHY (with answers), MATH (with answers section), CHEM (no answers) | 1,033 items. |
| Topic-wise test | All books | Use topic PDF pages + OCR text. Exercise questions are mapped to chapters, not to individual topics; topic-level tagging of questions is the next step. |
| Full-book / mixed test | All books | Except the C11-MATH missing units (G1). |
| Board-style paper | Class 12 only | `EXAM_BLUEPRINTS.md`. Needs official confirmation (roadmap §3). |

**Recommended next steps**
1. Obtain a complete Class 11 Mathematics file (G1), and the missing last page of the C12-MATH model paper (G2).
2. Extract the end-of-chapter questions into a structured item bank: one record per question with class, subject, book, chapter, question type, source PDF page, and verbatim stem/options transcribed from page images (needed for symbol-heavy items).
3. Tag each question to its topic ids (many-to-many), and author and review answer keys where the books provide none (§6.3).
4. Map SLO codes (printed in C11-CHEM and C12-CHEM; paraphrased SLOs in all books) to syllabus learning-outcome records, per roadmap §3.6.
5. Re-run `tools/verify_knowledge_base.py` after any change to `books/*.json`.

---

## 8. Completeness verification record (2026-10-06)

Second pass over both folders with `tools/verify_knowledge_base.py` and manual cross-checks:

| Check | Result |
|---|---|
| Every folder scanned (including nested) | ✅ 2 folders, no subfolders, 10 files, all PDFs |
| Every file inspected and indexed | ✅ 10 / 10 (all 2,488 pages OCR'd; TOCs read visually) |
| Every book in the master indexes | ✅ 5 in Class 11 index, 5 in Class 12 index |
| Every book has its chapters recorded | ✅ 122 chapters/units, each matched to the printed TOC (C11-MATH U7 recorded as *missing*) |
| Every TOC captured | ✅ 10 / 10, all printed TOC start pages match the actual chapter openers |
| Topics/subtopics mapped with pages | ✅ 1,796 numbered headings plus un-numbered sub-headings, each page inside its chapter range |
| Every PDF page accounted for | ✅ no page outside front matter / chapter / back-matter ranges |
| Class 11 and 12 not mixed | ✅ book class = folder class for all books; chapter-number continuity recorded explicitly |
| Source references correct | ✅ every `source_pdf` exists and page counts match; OCR layers have one block per PDF page |
| Duplicates / incomplete material flagged | ✅ §6.1–6.2 |
| Hand-written indexes consistent with JSON | ✅ SUBJECT_INDEX chapter titles and ranges: 0 mismatches |

---

## 9. Maintenance
- **Never modify** `11 Class Data/` or `12 Class Data/`. This knowledge layer sits on top of them.
- To correct or extend a book: edit `books/<ID>.json` (and the matching `books/<ID>.md`), then run
  `python education_knowledge/tools/build_indexes.py` and `python education_knowledge/tools/verify_knowledge_base.py`.
- To add a new file (e.g. a complete C11-MATH or a past paper): put it in the right class folder and OCR it with `tools/ocr_pdf.py` into `source_text/`. Create `books/<NEW_ID>.json/.md` (use a new ID such as `C11-MATH-v2` or `C12-PHY-PP2025`; never overwrite a different version), add it to `BOOK_CATALOG.md`, and re-run both tools. The verifier flags any un-indexed file.
