# education_knowledge/

Index and knowledge layer over the original textbook PDFs in `../11 Class Data/` and `../12 Class Data/`. The originals are read-only and are never modified.

**Start here → [`EDUCATION_DATA_ROADMAP.md`](EDUCATION_DATA_ROADMAP.md)** (lookup recipes, data model, gaps register, verification record).

| File | Use it for |
|---|---|
| [`BOOK_CATALOG.md`](BOOK_CATALOG.md) | What books exist, editions, what each contains, file status |
| [`SUBJECT_INDEX.md`](SUBJECT_INDEX.md) | Subject view; Class 11 ↔ 12 chapter numbering and links |
| [`CLASS_11_MASTER_INDEX.md`](CLASS_11_MASTER_INDEX.md) / [`CLASS_12_MASTER_INDEX.md`](CLASS_12_MASTER_INDEX.md) | Subject → Book → Chapter → Topic → Subtopic with PDF pages |
| [`CHAPTER_TOPIC_INDEX.md`](CHAPTER_TOPIC_INDEX.md) | Full-depth topic tree, key terms, formulas for every chapter |
| [`SOURCE_FILE_MAP.md`](SOURCE_FILE_MAP.md) | File ↔ chapter page ranges, page-number rules, file issues |
| [`QUESTION_INVENTORY.md`](QUESTION_INVENTORY.md) | Exercise question counts by type per chapter; answer availability |
| [`EXAM_BLUEPRINTS.md`](EXAM_BLUEPRINTS.md) | Class 12 pairing schemes, paper patterns, model papers |
| `books/<BOOK_ID>.md` / `.json` | Deep per-book analysis (source of truth) |
| `source_text/<BOOK_ID>.ocr.txt` | Searchable OCR text, page-marked by PDF page |
| `knowledge_map.json` | Everything in one JSON (class → subject → books) |
| `tools/` | OCR, page rendering, index rebuild, verification scripts |

Book IDs: `C11-PHY C11-CHEM C11-BIO C11-MATH C11-CS · C12-PHY C12-CHEM C12-BIO C12-MATH C12-CS`.
Page numbers are **PDF page indices** unless marked *printed*.
