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

## JSON (all kinds: `mcq`, `lesson`, `written`)

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

## CSV (multiple-choice questions only)

These are plain paragraphs. Use JSON for formulas, images or rich formatting.

Required columns: `external_id`, `chapter`, `title`, `stem`, `option_a`, `option_b`, `correct`.

Optional columns: `topic`, `option_c`, `option_d`, `explanation`, `difficulty`, `estimated_seconds`,
`cognitive_demand`, `source_document_id`, `pdf_from`, `pdf_to`.

- `correct` is the letter of the right option (`A` to `D`). Options get the stable IDs `o1` to `o4`.
- Unknown columns are rejected, so a misspelt header can't silently drop data.

Excel users: save as **CSV UTF-8**.

## Not imported here

- Marking rubrics. Attach them to a written question in the studio.
- Media files.
- Teacher labels, held-out evaluation evidence and student scripts. These stay private and separate (W01).

## Export (P06.S4.T2, EXPORT-01)

Publishers (with MFA) can download one class and subject at a time from **Studio → Export**
(`GET /v1/studio/export?grade=11&subject=chemistry`). The download is a JSON document with:

- `format: "portal-content-export"` and `schema_version: 1`;
- the book: title, source ID and publication-rights status;
- every chapter and topic, with its stable key, number and title, and whether it is retired;
- every item in that scope, with:
  - its `external_id` (if imported), kind, chapter and topic keys, state, availability, quarantine level and reading tier;
  - **all versions**: number, status, content schema version, body, source references and publication time;
  - any MCQ score corrections.

Exports never include learner data, attempts, staff identities or internal notes. Each export is audited with its
item count and size.

To re-import an exported item as a new draft, put `chapter`, `title`, the chosen version's `body` and `source_refs`,
and an `external_id` into an import file (see above).
