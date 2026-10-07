# Public-repository content audit

**Date:** 2026-10-07 · **Commit audited:** `main` @ `2db267e` plus this branch · **Repository visibility:** public (BLOCKERS B12)

`.gitignore` only prevents *future* additions, so tracked content was checked directly.

| Check | Method | Result |
|---|---|---|
| Source PDFs, page scans, images of textbook pages | `git ls-files` filtered for pdf/png/jpg/tiff/webp/docx/pptx/zip | **None.** The only images are Expo template app icons and the web favicon |
| Full-text OCR / extracted layers | path check (`education_knowledge/source_text/` is untracked) | **Not tracked** |
| Verbatim textbook text inside tracked indexes | `education_knowledge/tools/overlap_audit.py`: 12-word shingles from all 10 local text layers (752,001 shingles) compared with every tracked text file outside `apps/`, `packages/`, `Road Map/` (102 files) | Longest verbatim run anywhere = **39 words**. Shingle hit rate ≤ 1.5% per file. The longest runs are data-table values (e.g. enzyme optimum pH table) and figure captions, i.e. index reference metadata, not prose passages |
| Credentials / keys | regex scan for AWS keys, private-key blocks, GitHub tokens, live API keys and password assignments | **None** outside tests. Test fixtures use technical passwords only |
| Personal data | review | Only book credit names (authors, editors, reviewers, publishers) as printed in the public textbooks, held in book metadata. No learner or staff personal data is tracked |

**Rule going forward:** keep PDFs, page renders and full text out of commits. Re-run `python education_knowledge/tools/overlap_audit.py <out.json>` (needs the local text layers) before committing new index or derived-content files. Derived teaching content (lessons/questions) will live in the database/CMS, not in this repository.
