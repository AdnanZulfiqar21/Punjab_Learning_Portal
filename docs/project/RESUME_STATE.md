# RESUME STATE

**Updated:** 2026-10-08 (after the PR #31 review, "RS31"). Regenerated from `git log origin/main`, `gh pr list` and test runs.

## Repository state
- `main` = PRs #1 and #3–#30 merged (PR #2 closed unmerged). Latest: #28 `36b4612` (OCT8-05), #29 `2fb73cc` (OCT8-07), #30 `c6ffa04` (OCT8-06 and records).
- **Open:** PR #31 `feat/written-rescans` (W04.S3.T2/W06.S2.T4, RESCAN-01, plus the RS31 corrections in RESCAN-02). Merge on a green CI run of its exact head.
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
| RS31-01 rescan retry/race | Fixed, PR #31, RESCAN-02 (idempotency key; 409 `SAME_FILE`, never 500). |
| RS31-02 learner deadline | Fixed, PR #31, RESCAN-02 (durable obligation; deadline fixed at first release). |
| RS31-03 `post_cutoff` | Fixed, PR #31, RESCAN-02; one dev record corrected by `portal-written-repair`. |
| RS31 section 4 evidence provenance | Built, PR #31: `evidence_revisions` on each score version. |

## Test evidence (local, this machine; CI runs are on each PR)
| Commit / branch | Command | Result |
|---|---|---|
| `feat/oct8-detail-view` @ `758b8dc` | `uv run pytest -q` in `apps/api` | 190 passed |
| `feat/written-rescans` (RS31 corrections) | `uv run pytest -q` in `apps/api` | 204 passed |
| same | `npx playwright test` in `apps/web` (API and web running) | 41 passed, 22 skipped, 2 failed, 3 did not run. Both failures (studio concurrent edits, support question report) passed when rerun alone (2 passed); treated as load flakiness, not as passing evidence |
| PR #25 body (159) vs final report (172) | 159 was on `fix/pool-saturation` alone; 172 after merging #24 into it | Both correct for their commit |

## Next actions
1. Merge PR #31 on green CI of its exact head.
2. Deployment prerequisites (when B03 exists): run `portal-written-previews` and `portal-written-repair` once; schedule `portal-written-sweep-orphans` and `portal-written-learner-deadlines` (hourly); set review capacity per scope; set `PORTAL_TRIAL_DEVICE_EVIDENCE` and a secret `PORTAL_TRIAL_REF_PEPPER`. Production must not silently use `fallback` as the anti-repeat-trial implementation.
3. Roadmap continuation, in order: linked new practice attempts (W04.S3.T3, **next unblocked**); administrative regrades and adjudication (W06.S2.T3, same lock order and rebase path as PUB-01); native written capture, results, rescans (with the `Idempotency-Key` header) and mobile help; notifications (P15.S1); CMS import batches, previews, release/rollback, export (P06); source-grounded drafting and media (P07, drafts only); automatic written-assessment contracts (W05; no real script calls until B10).
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

## Do not redo
Book indexing (v2, `education_knowledge/`), OCR layers (local only), source checksums.

## Owner inputs that block dependent work
B01 reviewers and rights confirmation (academic publication), B03 cloud and object storage, B04 identity tenant, B05 media provider, B06 payments, B07 store accounts, B08 Android recall approval, B10 written-assessment provider, B13 Android SDK licence acceptance (native builds).
