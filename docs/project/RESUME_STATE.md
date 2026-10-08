# RESUME STATE

**Updated:** 2026-10-08 · regenerated from `git log origin/main` and open PRs (review R09).

## Repository state
- `main` = PRs #1 and #3–#18 merged (PR #2 closed unmerged). Last merge: #18, trial/entitlements/allowance (`b9250a0`).
- **Open:** PR #19 `feat/support-recheck`: support (IMPL-23), recheck correction RECHECK-01 (review R04) and the dev-issuer race fix REL-01 (review R08).
- **Gate:** `main` has no branch protection or ruleset (checked 2026-10-08 with the GitHub API). The CI workflow (changes, api, web, mobile, content jobs) is the only check, and it is not marked required. Merge only on a green run of the exact head being merged.
- **Git rules (GIT-01):** never rebase, amend pushed commits or force-push (including `--force-with-lease`). Merge `main` into feature branches. Merge stacked PRs base-first.

## What is merged (by area)
| Area | Records | Verification |
|---|---|---|
| Source registry, stable-ID catalogue, catalogue web journey | IMPL-08, IMPL-10, IMPL-11 | CI verified |
| Identity core, roles, MFA gating, audit; app sessions and web BFF; native auth | IMPL-07, IMPL-09, IMPL-12, IMPL-13 | CI verified; native = Expo web only |
| Editorial workflow, studio UI, lessons on web/mobile | IMPL-14, IMPL-15 | CI verified |
| MCQ items, attempt protocol §10.5, practice UI web/mobile | IMPL-16 to IMPL-18 | CI verified; mobile = Expo web only |
| Written records, attempts, teacher marking | IMPL-19 to IMPL-21 | CI verified; upload validation defective (R01/R02) |
| Trial, entitlements, allowance ledger | IMPL-22 | CI verified; R03/R05/R06 gaps open |

No academic content is published: B01 (reviewers) and rights confirmation block it. Readiness gates: **Platform Ready, Content Ready and Public Launch Ready are all unmet.**

## Review findings (2026-10-08) and status
| ID | Finding | Status |
|---|---|---|
| R01 | Upload validator accepts invalid PNG/PDF, rejects valid object-stream PDF | **Reproduced**; fixing next (`fix/written-evidence`) |
| R02 | Page cap counts files, not PDF pages; storage I/O under the attempt lock | Open; same branch as R01 |
| R03 | Concurrent starts can pass the two-permit check | Open; reproduce on PostgreSQL first |
| R04 | Recheck policy vs implementation | **Fixed in PR #19** (RECHECK-01) |
| R05 | Whole-script consumption; no per-question allocations | Open |
| R06 | Same-device trial protection not built | Open; account-level only |
| R07 | All published lessons public | Open; needs preview/premium classification |
| R08 | 401 after sign-up; search 503 | 401 **fixed** (REL-01); 503 open |
| R09 | Stale records | This file regenerated; register labels reconciled |

## Next actions (in order)
1. Merge PR #19 after a green CI run on its final head.
2. R01 + R02 on `fix/written-evidence`: Pillow + pypdfium2 (permissive licences; PyMuPDF avoided as AGPL), bounded decoding in a separate worker process, logical pages, per-PDF-page mapping, storage outside the lock. The parked dependency change is in `git stash` ("r01-deps").
3. R03: serialized per-account permit admission, with real concurrent PostgreSQL tests.
4. R07, then R05, then R06 contracts.
5. R08 search 503: bounded mixed-load reproduction.
6. Roadmap: rescan classification and regrades (W06.S2.T3/T4); native written capture and mobile help; notifications; CMS import/preview/release/export; media/storyboard; production adapters as prerequisites allow; automatic written-assessment contracts (no real provider calls until B10).

## Run locally
```bash
docker compose -f infra/docker-compose.yml up -d
cd apps/api && uv sync && uv run alembic upgrade head && uv run portal-import-catalogue --apply
uv run uvicorn portal_api.main:app --host 127.0.0.1 --port 8100
cd ../web && pnpm install && pnpm build && pnpm start      # http://localhost:3100
pnpm exec playwright test                                   # needs API + web running
uv run portal-dev-seed-staff                                # (in apps/api) dev-only staff fixtures incl. reviewer2 and support
uv run portal-dev-seed-practice                             # (in apps/api) dev-only labelled fixture questions
cd ../mobile && npx expo start --web --port 8190            # mobile screens on the web target (not native evidence)
```

## Gotchas
- Search 503 under 3-worker local E2E load is unexplained (R08). 503s log the DB error class and correlation ID (`portal_api.db`).
- The API has no auto-reload in these runs; restart it after API code changes before E2E.
- `curl localhost` on this machine adds about 250 ms (IPv6 fallback); use `127.0.0.1` for timings.
- Run Expo without `CI=1`: CI mode turns off Metro's file watching and serves stale bundles.
- Playwright `toHaveURL(/\/x$/)` also matches `/signin?next=/x`; anchor on `:\d+\/x`.
- Git Bash heredocs break on some quoting; write scripts to the scratchpad instead.

## Do not redo
Book indexing (v2, `education_knowledge/`), OCR layers (local only, `source_text/`, git-ignored), source checksums.

## Owner inputs that block dependent work
B01 reviewers and rights confirmation (academic publication), B03 cloud/object storage, B04 identity tenant, B05 media provider, B06 payments, B07 store accounts, B10 written-assessment provider, B13 Android SDK licence acceptance (native builds).
