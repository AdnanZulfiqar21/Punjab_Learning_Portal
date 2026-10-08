# RESUME STATE

**Updated:** 2026-10-08 (after PR #33; W06.S2.T3 in progress). Regenerated from `git log origin/main`, `gh pr list` and test runs.

## Repository state
- `main` = PRs #1 and #3–#33 merged (PR #2 closed unmerged). Latest: #31 `87c720f` (W06.S2.T4 rescans + RS31 corrections; CI run 37791799813 on head `27e9f84`), #32 `2277a6a` (W04.S3.T3 linked practice; CI run 37810869785 on head `dad3222`), #33 `41ac6d9` (PR32 review corrections; CI run 37834522031 on head `f5ccdf0`).
- **Open:** `feat/rubric-adjudication` (W06.S2.T3, ADJ-01). Merge on a green CI run of its exact head.
- **Gate:** `main` has no branch protection or ruleset. The CI workflow is the only check and is not marked required. Merge only on a green run of the exact head being merged. CI `mobile`/`content` jobs skip when their paths are unchanged; a skip is not mobile or content qualification.
- **Git rules (GIT-01):** never rebase, amend pushed commits or force-push (including `--force-with-lease`). Merge `main` into feature branches.

## What is merged (by area)
| Area | Records | Verification |
|---|---|---|
| Source registry, stable-ID catalogue, catalogue web journey | IMPL-08, IMPL-10, IMPL-11 | CI |
| Identity, roles, MFA, audit; sessions and web BFF; native auth | IMPL-07, IMPL-09, IMPL-12, IMPL-13, REL-01 | CI; native = Expo web only |
| Editorial workflow, studio UI, lessons web/mobile; premium lessons and previews | IMPL-14, IMPL-15, ACCESS-02 | CI |
| MCQ items, attempt protocol §10.5, practice UI web/mobile | IMPL-16 to IMPL-18 | CI; mobile = Expo web only |
| Written records, attempts, evidence parsing, logical pages, no connection held during slow work | IMPL-19, IMPL-20, EVIDENCE-01, DBHOLD-01 | CI |
| Teacher marking, rechecks, per-question outcomes, completion cases, serialised publication, per-question appeals | IMPL-21, RECHECK-01, ALLOC-01, PUB-01 | CI |
| Trial, entitlements, per-question allowance, permit admission, capacity | IMPL-22, ADMIT-01, ALLOC-01 | CI |
| Trial claims and device contracts (fixture-tested only) | TRIAL-02 | CI; **same-device requirement not met** |
| Support, question reports, staff queue | IMPL-23 | CI |
| One engine per process; pool saturation answered as 503 | REL-02 | CI |

No academic content is published: B01 (reviewers) and rights confirmation block it. **Platform Ready, Content Ready and Public Launch Ready are all unmet.**

## Review findings and status
| ID | Status |
|---|---|
| R01, R02 (uploads, logical pages) | Fixed and merged (#20). The connection-hold claim in EVIDENCE-01 was wrong; corrected by DBHOLD-01 (#26). |
| R03 (two-permit race) | Fixed and merged (#21). Clock placement refined by ADMIT-02 (OCT8-07). |
| R04 (recheck policy) | Fixed (#19); publication and appeal gaps fixed by PUB-01 (#27). |
| R05 (per-question allowance) | Fixed (#23); all-unanswered settlement in ALLOC-02 (OCT8-05, PR #28). |
| R06 (repeat trials on a device) | Contracts merged (#24). **Not met**: no real device evidence (B07/B08/B13), no per-request attestation. |
| R07 (all lessons public) | Fixed and merged (#22). Future media must use the same check. |
| R08 (401; search 503) | 401 fixed (REL-01). Pool saturation and cold-start engine race fixed (REL-02). **The original driver OperationalError 503 is still unexplained**; 503s log class and correlation ID. |
| OCT8-01 connection holds | Fixed and merged (#26), DBHOLD-01. Also fixed a late-upload admission found while reproducing. |
| OCT8-02/03/04 publication, pending work, appeals | Fixed and merged (#27), PUB-01. |
| OCT8-05 empty seal | Fixed and merged (#28), ALLOC-02. |
| OCT8-06 detail view | Built and merged (#30), DETAIL-01. Readability with real scripts not qualified. |
| OCT8-07 start clock | Fixed and merged (#29), ADMIT-02. |
| RS31-01 rescan retry/race | Fixed and merged (#31), RESCAN-02 (idempotency key; 409 `SAME_FILE`, never 500). |
| RS31-02 learner deadline | Fixed and merged (#31), RESCAN-02 (durable obligation; deadline fixed at first release). |
| RS31-03 `post_cutoff` | Fixed and merged (#31), RESCAN-02; one dev record corrected by `portal-written-repair`. |
| RS31 section 4 evidence provenance | Built and merged (#31): `evidence_revisions` on each score version. |
| PR32-01 omitted learner action | Fixed and merged (#33), REVIEW-PR32 (obligation authoritative; no silent withdrawal). |
| PR32-02 incomplete staff drafts | Fixed and merged (#33), REVIEW-PR32 (`draft_intent`, `draft` projection, workspace restore; proposals never applied). |
| PR32-03 linked-form autoflush race | Reproduced (UniqueViolation via autoflush at linked.py:132) and fixed; merged (#33). |
| PR32-04 cutoff label, records | Fixed and merged (#33) (`cutoff_timing`; records refreshed). |

## Test evidence (local, this machine; CI runs are on each PR)
| Commit / branch | Command | Result |
|---|---|---|
| `feat/oct8-detail-view` @ `758b8dc` | `uv run pytest -q` in `apps/api` | 190 passed |
| `feat/written-rescans` (RS31 corrections) | `uv run pytest -q` in `apps/api` | 204 passed |
| `feat/linked-practice-attempts` | `uv run pytest -q`; `npx playwright test` (API and web running) | API suite passed (exit 0; includes 3 new tests); E2E 46 passed, 22 skipped |
| `feat/written-rescans` @ `27e9f84` | `npx playwright test` in `apps/web` (API and web running) | 41 passed, 22 skipped, 2 failed, 3 did not run. Both failures (studio concurrent edits, support question report) passed when rerun alone (2 passed); treated as load flakiness, not as passing evidence |
| `fix/pr32-review` | `uv run pytest -q tests/test_pr32_corrections.py` | before the fix: 7 failed, 1 passed; after: 8 passed |
| same | `uv run pytest -q` in `apps/api` | 215 passed, 0 failed |
| same | `npx playwright test` in `apps/web` (API and web running) | 46 passed, 22 skipped, 0 failed |
| `feat/rubric-adjudication` | `uv run pytest -q` in `apps/api` (run alone; real exit code) | 220 passed, exit 0 (an earlier run showed 4 false failures because a second pytest session reset `portal_test` mid-run) |
| same | `npx playwright test` (API and web running, nothing else) | 47 passed, 23 skipped, exit 0 |
| PR #25 body (159) vs final report (172) | 159 was on `fix/pool-saturation` alone; 172 after merging #24 into it | Both correct for their commit |

## Intermittent test failures (bounded record; not fixed)
| Seen | Tests | Observation | Status |
|---|---|---|---|
| 2026-10-08, full E2E on `feat/written-rescans` @ `27e9f84` (3 workers) | `studio.spec.ts:88` concurrent edits; `support.spec.ts:66` question report | Failed in the full run, passed when rerun alone and in the next two full runs | **Root cause unknown.** Later green runs are not a fix. Re-examine if either fails again (capture the trace; suspect shared fixture accounts under parallel workers). |
| 2026-10-08, full E2E on `feat/rubric-adjudication` while a second pytest run was loading the machine | `catalogue.spec.ts:3` Class XII region not visible; `lessons.spec.ts:20` timeout | Did not recur in the next full run made alone (47 passed) | **Not proven** to be load-related; re-examine if seen without concurrent load. |

## Next actions
1. Merge `feat/rubric-adjudication` on green CI of its exact head.
2. Deployment prerequisites (when B03 exists): run `portal-written-previews` and `portal-written-repair` once; schedule `portal-written-sweep-orphans` and `portal-written-learner-deadlines` (hourly); set review capacity per scope; set `PORTAL_TRIAL_DEVICE_EVIDENCE` and a secret `PORTAL_TRIAL_REF_PEPPER`. Production must not silently use `fallback` as the anti-repeat-trial implementation.
3. Roadmap continuation, in order: (done: linked new practice attempts, W04.S3.T3, LINKED-01); (done on `feat/rubric-adjudication`: rubric adjudications across attempts, W06.S2.T3, ADJ-01; run `portal-written-regrade` after each approved correction); native written capture, results, rescans (with the `Idempotency-Key` header) and mobile help (**next unblocked**); notifications (P15.S1); CMS import batches, previews, release/rollback, export (P06); source-grounded drafting and media (P07, drafts only); automatic written-assessment contracts (W05; no real script calls until B10).
4. Outstanding, not met: native repeat-device protection (R06; B07/B08/B13), native Android/iOS verification, approved academic content (B01), automatic-marking qualification (B10), production load evidence, and the original unexplained OperationalError (R08).

## Run locally
```bash
docker compose -f infra/docker-compose.yml up -d
cd apps/api && uv sync && uv run alembic upgrade head && uv run portal-import-catalogue --apply
uv run uvicorn portal_api.main:app --host 127.0.0.1 --port 8100
cd ../web && pnpm install && pnpm build && pnpm start      # http://localhost:3100
pnpm exec playwright test                                   # needs API + web running
uv run portal-dev-seed-staff && uv run portal-dev-seed-practice   # (in apps/api) dev-only fixtures
cd ../mobile && npx expo start --web --port 8190            # Expo web target (not native evidence)
```

## Gotchas
- Stopping a background task can leave its uvicorn or Expo child holding the port; check `Get-NetTCPConnection -LocalPort <port>` and stop that PID.
- The API runs without auto-reload here; restart it after API changes before E2E.
- `git push` can hang on the Windows credential manager; use `git -c credential.helper= -c credential.helper='!gh auth git-credential' push`.
- Git Bash heredocs break on some quoting; write scripts to the scratchpad instead.
- `curl localhost` adds about 250 ms (IPv6 fallback); use `127.0.0.1` for timings.
- Run Expo without `CI=1` (no file watching otherwise).
- Never run two `pytest` sessions at once: conftest resets the shared `portal_test` database at session start, so a second run wipes the first one's data mid-run (this caused 4 false failures on 2026-10-08). Read pytest's real exit code; `| tail` hides it.

## Do not redo
Book indexing (v2, `education_knowledge/`), OCR layers (local only), source checksums.

## Owner inputs that block dependent work
B01 reviewers and rights confirmation (academic publication), B03 cloud and object storage, B04 identity tenant, B05 media provider, B06 payments, B07 store accounts, B08 Android recall approval, B10 written-assessment provider, B13 Android SDK licence acceptance (native builds).
