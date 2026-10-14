# Import worker: deployment contract

Covers IMPORT-BULK-01, hardened by the review of 2026-10-14 (OCT14-02, OCT14-03, OCT14-05). Written for the PR #188
review, gap 4. No production resources exist yet: hosting and object storage wait on B03. This page states what a
deployment must provide, and what was rehearsed locally.

## What runs

| Process | Count | Does |
|---|---|---|
| API (`uvicorn portal_api.main:app`) | every replica | Streams a large import (up to 50 MB and 20,000 rows) to `PORTAL_IMPORT_DIR` and records a queued batch. |
| `portal-import-worker` | 1 or more, long-lived | Claims queued batches. Checks their rows, or commits them, and deletes the upload once its rows are stored. |
| `portal-import-reconcile --apply` | hourly, scheduled | Deletes uploads that no batch names and that are over an hour old: the API stopped between writing a file and recording its batch. Without `--apply` it only lists them. |

All three belong to the **bulk** capacity class (`budget.py`, `docs/project/CAPACITY_BUDGET.md`): a database pool of
3 per process.

## Shared private storage: required

- **One namespace.** Every API replica and every worker must see the same `PORTAL_IMPORT_DIR`, as one file system
  shared across hosts. A directory with the same name on different hosts is *not* enough. A worker that can't see the
  file fails the batch with "The uploaded file is missing", and the author has to upload it again.
- **Durable.** Queued batches wait for a worker, across restarts and deploys, so the storage can't be a tmpfs or a
  container's own disk.
- **Private.** It is never served by the web tier. Only the service user can read it (mode 0700). It holds authors'
  draft files, never learners' data.
- **Object storage later.** When B03 provides object storage, the same key layout (`<uuid>.upload`) moves to a private
  bucket. The worker's `_root()` and `_remove()` are the only places that touch files.

## Supervision and restarts

- **Run as a service** that restarts automatically (container `restart: always`, or systemd `Restart=always`).
- **More than one worker is safe.** Each claim takes the oldest waiting batch with `SKIP LOCKED` and stamps it with a
  claim token. Every write is fenced by that token and the expected status, so a stale worker changes nothing
  (OCT14-02).
- **A worker stopped part-way is recovered automatically.** Its lease runs out after 2 minutes; another worker then
  resumes validation after the last stored chunk of 250 rows. A commit is one transaction, so an interrupted commit
  rolls back and is run again. Nothing needs resetting by hand.
- **Bad input** fails at once, with the reason shown to the author. This covers an unreadable, damaged, encrypted or
  invalid file, an author who is suspended or lost the role, or a preview that is out of date.
- **Anything else** (database, storage, a bug) releases the batch for another try after 30 s, doubling each time up
  to 15 min. After 5 claims it fails, telling the author it was a problem on our side (OCT14-03). One bad batch never
  stops the rest of the queue.

## Health

- **Signal:** `content_import_queue_age_s` is the age of the oldest batch still queued, being checked or being
  committed. It warns at 15 min and alerts at 1 h; runbook `docs/runbooks/alerts.md#import-backlog`.
- **Logs:** the worker logs each unexpected error to stderr with its batch ID, and keeps the last one in
  `content_import_batch.last_error`, for operators only. A failed batch's `failure` is what the author sees.

## Capacity (planning numbers, not measurements)

- A worker holds one batch at a time: the file (≤ 50 MB) and its parsed rows (≤ 20,000).
- Allow at least 1 GB of memory per worker container.
- Throughput and latency haven't been measured. That is part of the load qualification (P20), on representative
  staging (B03).

## Local rehearsal (2026-10-14; no spending, no production resources)

1. API on port 8100 against the local PostgreSQL (`infra/docker-compose.yml`, dev database on 57432).
2. Six bulk CSV batches queued through `POST /v1/studio/imports/bulk` with the seeded fixture author. Each had 400
   fixture rows naming a chapter that doesn't exist, so the check runs fully but nothing could ever be written.
3. Two `portal-import-worker --once` processes started at the same time.

**Result:** each worker handled 3 batches. All 6 became previews, each with exactly one `content.import_previewed`
audit entry and 400 distinct rows. Every upload was deleted, and attempts were reset to 0.
`portal-import-reconcile` then found 0 orphans.

The two-session takeover, bad-input, retry, suspension and orphan cases are covered by
`apps/api/tests/test_import_worker_hardening.py` (PostgreSQL). Not rehearsed: a shared file system across real
hosts, a host restart mid-commit, or load. All of these wait on B03 staging.
