# RESUME STATE

**Updated:** 2026-10-08 · regenerated from `git log origin/main` and open PRs (review R09).

## Repository state
- `main` = PRs #1 and #3–#22 merged (PR #2 closed unmerged).
- PR #19 (support, RECHECK-01, REL-01) merged as `7933843`; PR #20 (R01/R02, EVIDENCE-01) merged as `5df22fd` on 2026-10-08.
- PR #21 (R03, ADMIT-01) merged as `0f402d8`; PR #22 (R07, ACCESS-02) merged as `ac2220d`.
- **Open:** `fix/written-allocations` (R05, ALLOC-01).
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
| R01 | Upload validator accepts invalid PNG/PDF, rejects valid object-stream PDF | **Fixed and merged** (PR #20, EVIDENCE-01) |
| R02 | Page cap counts files, not PDF pages; storage I/O under the attempt lock | **Fixed and merged** (PR #20) |
| R03 | Concurrent starts can pass the two-permit check | **Fixed and merged** (PR #21, ADMIT-01) |
| R04 | Recheck policy vs implementation | **Fixed and merged** (PR #19, RECHECK-01) |
| R05 | Whole-script consumption; no per-question allocations | **Fixed** on `fix/written-allocations` (ALLOC-01) |
| R06 | Same-device trial protection not built | Open; account-level only |
| R07 | All published lessons public | **Fixed and merged** (PR #22, ACCESS-02) |
| R08 | 401 after sign-up; search 503 | 401 **fixed and merged** (REL-01); 503 open |
| R09 | Stale records | This file regenerated; register labels reconciled |

## Next actions (in order)
1. After deploying PR #20: run `portal-written-previews` once.
2. Schedule `portal-written-sweep-orphans` hourly wherever evidence is stored.
3. Merge the R05 PR after green CI. Operators must set review capacity (`PUT /v1/ops/written-capacity/{grade}/{subject}`) before written practice is offered in a scope.
4. R06 contracts (trial claims, device authorization, recovery).
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
- `git push` can hang on the Windows credential manager; push with `git -c credential.helper= -c credential.helper='!gh auth git-credential' push`.

## Do not redo
Book indexing (v2, `education_knowledge/`), OCR layers (local only, `source_text/`, git-ignored), source checksums.

## Owner inputs that block dependent work
B01 reviewers and rights confirmation (academic publication), B03 cloud/object storage, B04 identity tenant, B05 media provider, B06 payments, B07 store accounts, B10 written-assessment provider, B13 Android SDK licence acceptance (native builds).
