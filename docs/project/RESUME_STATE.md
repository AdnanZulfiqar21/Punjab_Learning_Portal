# RESUME STATE

**Updated:** 2026-10-07 · **Branches:** `feat/foundation-catalogue` (PR #1 → `main`), `feat/mobile-shell` (stacked on it) · **Base:** `main` @ `e026e67`

## Where we are
Waves A/B/D/E are in progress (roadmap §18). Done:
- Source intake registry and a curriculum catalogue built from the verified indexes.
- FastAPI backend with the curriculum module and migrations.
- Next.js web catalogue journey.
- Contracts package and CI.

Reviewed teaching content does not exist yet (BLOCKERS B01), so the vertical slice stops at textbook structure.

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
1. **Mobile native evidence (P13.S1/P01.S4.T1):** install the Android SDK/emulator or use EAS development builds (B07) and run the existing journey on a device; then the native capability spikes.
2. **Identity clients (P04.S1.T2/T3):** web sign-in via HTTP-only cookie BFF (+CSRF) and onboarding screens; mobile PKCE + secure token storage; session list/revoke. API identity core is done (IMPL-07).
3. **CMS foundations (P06):** staff roles, authoring/review workflow (author ≠ approver), import batch UI, publication validation. This lets reviewers work as soon as they are named.
4. **Question bank/attempt engine models (P08/P10):** MCQ versioning, immutable attempt snapshots, durable save protocol (§10.5) with tests. These can be built and tested with technical fixtures; no academic content is published.
5. **P01.S4.T2 rendering spike:** render real equations, chemistry and Urdu/English from source figures through the block registry.

## Do not redo
Book indexing (v2, `education_knowledge/`), OCR layers (local only, `source_text/`, git-ignored), source checksums.

## Open questions for the owner
See BLOCKERS B01 (reviewers: the critical path), B12 (repo visibility), rights confirmation (LAUNCH_MANIFEST).
