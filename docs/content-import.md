# Content import formats (P06.S2, IMPORT-01)

Staff who can draft content in a class and subject import questions and lessons in batches from **Studio → Import**,
or through `POST /v1/studio/imports`.

Every import works in two steps:

1. **Preview (dry run).** The whole file is checked and nothing is written to content. You see:
   - what each row would do;
   - every error and warning, by row;
   - a downloadable correction report (CSV, one line per row).
2. **Commit.** The rows are checked again against the current catalogue and written in **one transaction**: every
   row, or none. Rows that will become or update an item must be error-free first. Fix the file and preview it again.

An import only ever creates or updates **drafts**. Imported items go through the normal review, source-rights and
publication steps. Nothing is submitted, approved or published by an import. Never import invented or unreviewed
academic material as if it were approved; drafts still need a second person's review.

## Row actions

| Action | Meaning |
|---|---|
| `create` | New item. A draft is created with the row's content. |
| `update` | The `external_id` already exists as a draft (or "changes requested"), and the row differs. The draft is replaced, as the next revision of the same item. |
| `unchanged` | Same content as the last import of that `external_id`. Nothing is written. |
| `skip` | The item is in review, approved or published. Start a revision in the studio to change it. |
| `error` | The row breaks a rule. Nothing from the batch can be committed until it is fixed. |

`external_id` is your stable ID for a row, such as `CHEM11-CH03-MCQ-0042`. It must be unique per kind; at most 120
characters. Re-importing the same file is safe: every row comes back `unchanged`. Items never move between chapters
through an import.

## Limits

- At most 5 MB and 2,000 rows per file. Split larger sets.
- UTF-8 only. A byte-order mark is accepted.
- Previews expire after 24 hours.

## JSON (all kinds: `mcq`, `lesson`, `written`, `storyboard`, `rubric`, `passage`)

```json
{
  "schema_version": 1,
  "kind": "mcq",
  "items": [
    {
      "external_id": "CHEM11-CH03-MCQ-0042",
      "chapter": "<chapter stable key or ID>",
      "topic": "<optional topic stable key or ID within that chapter>",
      "title": "Short title for staff",
      "body": { "...": "the same body the studio editor saves for this kind" },
      "source_refs": [{ "source_document_id": "<textbook document ID>", "pdf_from": 41, "pdf_to": 42 }]
    }
  ]
}
```

The `body` follows each kind's content schema (§10.2, §10.7): blocks, formulas, images and options with stable IDs.
Source references must point to the chapter's own textbook, inside the PDF page range. Rows without references can be
imported but cannot be published until references are added.

### References to other items (IMPORT-REFS-01)

Each reference is an existing item's `external_id` (from an earlier import) or its ID. Import the referenced items first.

- **Rubrics** (`kind: "rubric"`) need `"question"`: the written question they mark, in the same chapter. The rubric is
  attached to that question and marks its current version, whatever `question_version_id` the body names. A question
  that already has another rubric is an error: change that rubric in the studio.
- **Variants** (`kind: "mcq"`) may give `"family"`: an existing question in the same chapter. The new question joins
  that question's family (P08.S3.T2).
- **Passages** (`kind: "passage"`) import like lessons (their `body` holds `blocks`). A question may then give
  `"passage"`: the passage it uses, which becomes its `passage_id`.

## CSV or Excel workbook (multiple-choice questions only)

These are plain paragraphs. Use JSON for formulas, images or rich formatting.

Required columns: `external_id`, `chapter`, `title`, `stem`, `option_a`, `option_b`, `correct`.

Optional columns: `topic`, `option_c`, `option_d`, `explanation`, `difficulty`, `estimated_seconds`,
`cognitive_demand`, `source_document_id`, `pdf_from`, `pdf_to`, `family` (an existing question this one is a variant
of).

- `correct` is the letter of the right option (`A` to `D`). Options get the stable IDs `o1` to `o4`.
- Unknown or repeated columns are rejected, so a misspelt or doubled header can't silently drop data.

**Templates.** The import page offers the headings as `mcq-template.xlsx` and `mcq-template.csv` (no rows). In the
workbook every column is formatted as text, so an external ID like `007` keeps its leading zeros, and the heading row
is frozen.

**Excel workbooks (.xlsx, IMPORT-XLSX-01).** Upload the `.xlsx` file itself; it goes through exactly the same checks
as the CSV file.

- Only the first worksheet is read. Rows with every cell blank are skipped.
- A formula's saved result is read, never the formula, so save the workbook in Excel before uploading.
- A column with values but no heading is an error.
- Not accepted: old `.xls` files, password-protected workbooks, and any workbook that declares a DOCTYPE or entities.
  A part that unpacks past 25 MB, more than 64 columns, or more than 2,000 rows is also refused.
- If a workbook won't read, save it as **CSV UTF-8** instead.

## Large files (IMPORT-BULK-01)

A preview in the page takes at most 5 MB and 2,000 rows. A larger file, up to **50 MB and 20,000 rows**, is checked by
the import worker instead. The import page does this by itself: it shows the batch as **Queued**, then **Checking
rows: N of M**, then the ordinary preview. You can leave the page and come back. A queued file can be cancelled.

- The rows are checked with exactly the same rules as a preview. The batch then expires like any other preview, a
  day after it is ready.
- Past 500 rows, the page lists only the rows with errors or warnings. The correction report lists every row.
- Importing more than 2,000 rows is also done by the worker. It writes every row in one transaction, or none. If a
  row changed after the preview (for example, it was imported separately), the batch **fails** with the reason, and
  nothing from it is imported. Upload the file again to get a fresh preview.
- The uploaded file is kept privately only until its rows are checked, and deleted then (or when the batch fails or
  is cancelled).
- API: `POST /v1/studio/imports/bulk?format=…&filename=…` (raw body) answers `202` with the queued batch. Poll
  `GET /v1/studio/imports/{id}`: it carries `rows_checked`, `rows_total` and, for a failed batch, `failure`.

## Media packs (MEDIA-MANIFEST-01)

Diagrams, handouts, captions and diagram sources can be added to the asset archive in bulk, from **Studio → Assets →
Media pack**. A pack is a `.zip` file, at most 60 MB, holding `manifest.json` at its top level and the files it lists:

```json
{
  "schema_version": 1,
  "kind": "media",
  "grade": 11,
  "subject": "biology",
  "items": [
    {
      "external_id": "bio11-ch1-fig-2",
      "kind": "image",
      "title": "Cell diagram, figure 2",
      "file": "figures/fig-2.png",
      "sha256": "optional: the file's SHA-256, checked when given",
      "provenance": { "source": "Who made it, from what", "author": "", "licence": "", "tool": "" }
    }
  ]
}
```

- `kind` is `image` (PNG or JPEG), `handout` (PDF), `caption` (WebVTT) or `diagram_source` (archived, never served).
  Each kind keeps its usual size limit, and every file is scanned and validated exactly like a single upload.
- `external_id` is the file's stable key within the class and subject. Importing the same pack again changes
  nothing. A changed file becomes that asset's next version; earlier versions are never overwritten. An existing key
  can't change its kind.
- `provenance.source` is required for every file. File names are exact paths inside the pack.
- A pack lists at most 200 files.
- **Check** previews every file and writes nothing. **Archive** checks everything again, then archives all the files
  or none. It only runs when the preview has no errors. If storage fails part-way, nothing is kept.
- After archiving, each file shows its version ID. Content cites that ID, for example an image's `asset_version_id`
  or a fallback's `image_asset_id`.
- Only content authors for the pack's class and subject can import it.

## Not imported here

- Media files inside a structured import (add them with a media pack or a single upload first, then cite their
  version IDs).
- Teacher labels, held-out evaluation evidence and student scripts. These stay private and separate (W01).

## Export (P06.S4.T2, EXPORT-01)

Publishers (with MFA) can download one class and subject at a time from **Studio → Export**
(`GET /v1/studio/export?grade=11&subject=chemistry`). The download is a JSON document with:

- `format: "portal-content-export"` and `schema_version: 2` (version 1 had no `concepts` or `assets`);
- the book: title, source ID and publication-rights status;
- every chapter and topic, with its stable key, number and title, and whether it is retired;
- every item in that scope, with:
  - its `external_id` (if imported), kind, chapter and topic keys, state, availability, quarantine level and reading tier;
  - **all versions**: number, status, content schema version, body, source references and publication time;
  - any MCQ score corrections;
- `concepts` (EXPORT-02): every concept of the subject that is mapped to a topic of this book, with its code, title,
  statement, status, publication time and source references, and:
  - `topics`: its topic keys **in this book only** (a concept also taught in the other class's book is mapped there too,
    but Class XI and XII are never mixed in one file);
  - `requires`: its prerequisites by concept code, with the bridging lesson's item ID if one is named;
  - `inclusion`: its syllabus inclusion records (scope, year, state, reason, source and source version, status,
    publication time);
- `assets` (EXPORT-02): one reference for every archived asset version that any exported version's body names
  (diagrams, handouts and fallback images): asset and version IDs, the asset's `external_id`, kind and title, the
  version number, media type, SHA-256 and size of the master, its dimensions or page count, delivery state and
  provenance (source, author, licence, tool). A reference to a version that no longer exists is listed with
  `missing: true`. The files themselves are not in the document; fetch them from the studio, and check them against
  the SHA-256.

Exports never include learner data, attempts, staff identities or internal notes. Each export is audited with its
item count and size.

To re-import an exported item as a new draft, put `chapter`, `title`, the chosen version's `body` and `source_refs`,
and an `external_id` into an import file (see above).
