# education_knowledge/ — Class 11 & Class 12 Academic Library Index

**Entry point → [`Academic_Library_Index_Manifest.md`](Academic_Library_Index_Manifest.md)**

The textbooks in `../11 Class Data/` and `../12 Class Data/` are the **source of truth** and are read-only. Everything here is a
navigation layer on top of them:

```
Original current PDF  →  per-book index  →  subject index  →  class master index
```

## Two separate knowledge bases
| | Class 11 | Class 12 |
|---|---|---|
| Master index | [`Class_11_Master_Index.md`](Class_11_Master_Index.md) | [`Class_12_Master_Index.md`](Class_12_Master_Index.md) |
| Per-book / subject indexes | `indexes/class_11/<subject>/` | `indexes/class_12/<subject>/` |
| Visual index (whole class) | `indexes/class_11/class_11_visual_index.md` | `indexes/class_12/class_12_visual_index.md` |
| Assessment index (whole class) | `indexes/class_11/class_11_assessment_index.md` | `indexes/class_12/class_12_assessment_index.md` |
| Machine-readable | `indexes/class_11/class_11_knowledge_map.json` | `indexes/class_12/class_12_knowledge_map.json` |

Each subject folder holds `<subject>_<class>_book_index.md` (book record, TOC, chapter index, assessment, issues),
`<subject>_<class>_visual_index.md` (every indexed visual with page, caption, labels, meaning) and
`<subject>_<class>_book.json` (source of truth for the generated files), plus the generated `<subject>_subject_index.md`.

## Routing rules for future requests
1. **"Class 11 …"** → use only `Class_11_Master_Index.md` and `indexes/class_11/`. **"Class 12 …"** → only Class 12. Never mix classes unless asked.
2. Route: Master Index → subject → book index → chapter → PDF pages → (visual / assessment entries) → open the original PDF pages to verify before generating material.
3. **Chapter numbers:**
   - Class 12 Physics, Chemistry and Biology number their chapters **continuing from Class 11**: Physics 13–21, Chemistry 17–33, Biology 13–25.
     - The Class 12 Physics Contents page numbers its chapters 1–9, so the index stores both numbers. "Class 12 Physics Chapter 3" means Physical Optics (Ch 15 in the book).
   - Mathematics and Computer Science restart at 1 in both classes.
   - If a request gives a subject and chapter but no class, and the class cannot be inferred, ask rather than guess.
4. Visual IDs look like `C11-BIO/Ch3/Fig3.12`, `C12-CHEM/Ch27/Tab27.1` or `C11-MATH/Ch6/Vis6-3`. A descriptive identifier without an official caption is marked "(descriptive)".
5. Text layers in `source_text/` are searchable by PDF page (`=====PAGE n=====`). OCR or extracted text garbles formulas, structures, code and tables, so always check those against the page image (`tools/render_pages.py`).

## Maintenance
```
python education_knowledge/tools/build_indexes.py                       # regenerate master/subject/visual/assessment indexes + manifest
python education_knowledge/tools/verify_knowledge_base.py --append-manifest   # quality-control pass, appends result to the manifest
```
Edit only the per-book `*_book.json` / `*_book_index.md` / `*_visual_index.md`, then re-run both commands.
`_archive/v1_2026-10-06_studyplusplus_scans/` holds the first index built from the earlier, replaced scans. It is **not authoritative**.
