# RESUME STATE

**Updated:** 2026-10-07 · **Branch:** `feat/mobile-auth` · PR #6 and PR #7 (web sessions) merged to `main`

## Where we are
Waves A/B/D/E are in progress (roadmap §18). Merged to `main`:
- Source registry and stable-ID catalogue (IMPL-08, IMPL-11).
- FastAPI curriculum module, identity core with roles, MFA gating and audit (IMPL-07, IMPL-09).
- Next.js catalogue journey with build-once runtime config (IMPL-10).
- Expo mobile shell, contracts package, CI.

Also merged: app sessions and the web BFF with sign-in, sign-out, protected routes, session list/revoke and onboarding (IMPL-12).

On `feat/mobile-auth`: native Account tab, secure-store sessions and onboarding (IMPL-13).

Reviewed teaching content does not exist yet (BLOCKERS B01), so learner pages stop at textbook structure.

## Run locally
```bash
docker compose -f infra/docker-compose.yml up -d
cd apps/api && uv sync && uv run alembic upgrade head && uv run portal-import-catalogue --apply
uv run uvicorn portal_api.main:app --host 127.0.0.1 --port 8100
cd ../web && pnpm install && pnpm build && pnpm start      # http://localhost:3100
pnpm exec playwright test                                   # needs API + web running
cd ../mobile && npx expo start --web --port 8190            # mobile screens on the web target (not native evidence)
```

## Next unblocked tasks (in order)
1. **Merge `feat/mobile-auth`** (merge `main` in; never rebase or force-push pushed branches, GIT-01).
2. *(done: native auth/onboarding, IMPL-13; PKCE waits for B04)*
3. **CMS foundations (P06):** staff workspace, import batch UI, draft editing, independent review (author ≠ approver), publication controls, audit history.
4. **Question bank/attempt engine (P08/P10):** versioned items and forms, MCQ runtime, durable saves (§10.5), deadlines, receipts. Technical fixtures only.
5. **Written assessment (W tasks):** question/rubric records, private scan upload, page mapping, receipts, reviewer workflow.
6. **Native evidence:** JDK 17 and Android cmdline-tools are in `%USERPROFILE%\devtools`. Installing SDK packages needs the owner to accept the Android SDK licence (BLOCKERS).

## Do not redo
Book indexing (v2, `education_knowledge/`), OCR layers (local only, `source_text/`, git-ignored), source checksums.

## Open questions for the owner
See BLOCKERS B01 (reviewers: the critical path), B12 (repo visibility), rights confirmation (LAUNCH_MANIFEST).
