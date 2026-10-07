# IMPLEMENTATION REGISTER (P00.S3.T1)

Source plan: `Road Map/Punjab_Learning_Portal_Master_Roadmap_v2.2_Integrated_Written_Assessment.md` (current reference; 306 core + 117 written task IDs). Task state and gate state are recorded separately (roadmap §7, §7.2). **Any task not listed is `TODO`.** States: TODO · IN_PROGRESS · BLOCKED_EXTERNAL · BLOCKED_DECISION · IMPLEMENTED · VERIFIED · ACCEPTED.

## Tasks touched

| Task | State | Evidence / code | Checks | Remaining |
|---|---|---|---|---|
| P00.S1.T1 Owner requirements | IN_PROGRESS | DECISIONS SCOPE-01/AUTH-01, LAUNCH_MANIFEST | — | Requirement→phase/AC trace table |
| P00.S1.T2 Release boundaries | IMPLEMENTED | RELEASE_CHECKLIST (3 readiness states) | — | Owner acceptance |
| P00.S2.T1 External dependency register | IMPLEMENTED | BLOCKERS B01–B12 | — | Owner/lead times |
| P00.S2.T2 Content responsibility | BLOCKED_EXTERNAL | BLOCKERS B01 (reviewers), LAUNCH_MANIFEST rights UNVERIFIED | — | Named reviewers; rights confirmation |
| P00.S3.T1 Implementation register + control files | IMPLEMENTED | this file, RESUME_STATE, DECISIONS, BLOCKERS, DEPENDENCIES, RELEASE_CHECKLIST | — | Keep current |
| P00.S3.T4 Dependencies / gate scopes | IMPLEMENTED | DEPENDENCIES (Section 18 waves) | — | Per-task effort estimates after spikes |
| P22.S1 (identity & metadata hardening) | IMPLEMENTED | Stable ID registry + retirement (IMPL-08); exact edition/curriculum/session/numbering metadata (IMPL-11); public-repo audit (`PUBLIC_REPO_AUDIT.md`) | `content/tools/test_identity.py` 8/8; `test_catalogue_identity.py`; no-reset re-import of dev DB 0/0/0 | Reviewer confirmation of XII Physics display mapping; source rights |
| P01.S1.T4 (web runtime config) | VERIFIED (local) | `instrumentation.ts` startup validator, exit 78; per-request origin (IMPL-10) | Same build → two origins (12 vs 11 chapters); prod without/with dev origin → 78; CI repeats refusal checks | Staging/production deploy evidence (B03) |
| P22.S1 Source intake (books) | IMPLEMENTED | `content/source_registry.json` (10 sources, SHA-256, completeness, rights note); `education_knowledge/` v2 indexes; `content/tools/build_catalogue.py --check` | checksums OK ×10 (2026-10-06) | Rights confirmation; named reviewers; RCS selection (P22.S1.T3) |
| P01.S1.T1 Pin stack | IMPLEMENTED | docs/project/STACK.md, lockfiles | — | Mobile stack at P13.S1 |
| P01.S1.T2 Module boundaries | IN_PROGRESS | `apps/api/src/portal_api/modules/{curriculum,system}` | — | Remaining domains as built |
| P01.S1.T4 Configuration/artifact model | IN_PROGRESS | `portal_api/config.py` startup validator; `/v1/runtime-config`; web reads API origin at runtime, refuses missing origin in staging/production | `test_config.py` (4 tests) | Release manifest, native variants |
| P01.S2.T1 Entities/constraints (curriculum slice) | IMPLEMENTED | `modules/curriculum/models.py`, migration `20261006_4ee482d111db` | `alembic check` clean | Other domains |
| P01.S3.T1 API contract | IMPLEMENTED (catalogue slice) | `packages/contracts/openapi.json` + generated TS types; RFC 9457 errors | CI drift checks (OpenAPI + TS) | Versioning policy doc as API grows |
| P03.S1.T1 Workspace scaffold | IMPLEMENTED | monorepo layout (IMPL-03) | — | `apps/mobile` |
| P03.S1.T2 Local services | IMPLEMENTED | `infra/docker-compose.yml` (Postgres 17, Valkey, SQS emulator) | started locally | Object storage emulator |
| P03.S1.T3 Conventions | IN_PROGRESS | ruff/mypy strict, ESLint, `.gitattributes` LF, commit style | — | CONTRIBUTING notes |
| P03.S2.T3 Environment validation | IMPLEMENTED | Settings validator; `/healthz`, `/readyz` (DB + migration head) | tests pass | Secrets store integration (B03) |
| P03.S3.T1 Change checks | IMPLEMENTED | `.github/workflows/ci.yml` (path-filtered content/api/web jobs, E2E) | first run on PR | — |
| P03.S4.T1 Vertical slice | IN_PROGRESS | Web catalogue journey on real imported structure (Learn → book → chapter → topics, search) | Playwright 10/10 (desktop + phone) on production build | Needs a **reviewed lesson with a scientific block** (B01) and native builds |
| P03.S4.T2 Correlation ID | IMPLEMENTED (API + web→API) | `observability.py`; web sends `X-Correlation-ID` | test_correlation_id… | Jobs/outbox propagation |
| P03.S4.T3 Clean install | IN_PROGRESS | migrations from empty DB in tests; disposable-only reset guard | test DB reset each run | Documented fresh-checkout run in CI |
| P05.S1 (curriculum model, catalogue) | IMPLEMENTED (structure) | importer (dry-run default, idempotent upsert, no deletes, validation, batch record); read API; trigram search with grade labels | `test_importer.py` (4), `test_catalogue_api.py` (9) | Outcome mapping, board inclusion, exam profiles (P05.S2/S3) |
| P13.S1 Native app shell | IN_PROGRESS | `apps/mobile`: Expo SDK 57 + expo-router; Learn (XI/XII separate), book, chapter (topic tree, source pages), Search; loading/error-retry/not-found states; variant identities + required API origin (IMPL-06) | typecheck, expo lint, expo-doctor 21/21; journey verified on the **Expo web target** against the real API | **No native device/emulator evidence yet**: no Android SDK on this machine; iOS needs macOS/EAS (B07, B09). Secure storage/OIDC/billing/attestation spikes (P01.S4.T1) |
| P04.S1.T1 Registration/verification | IN_PROGRESS | Dev-only issuer register/token (enumeration-safe, argon2, timing-equalised); real verification/recovery belongs to the managed IdP (B04) | `test_identity.py` | Cognito tenant; email verification; abuse controls at the IdP |
| P04.S1.T2 Login/recovery | IN_PROGRESS | Token verification (`modules/identity/tokens.py`); app sessions (`sessions.py`, IMPL-12); web BFF sign-in/sign-out, HTTP-only cookie, Server Action CSRF, protected routes, session list/revoke (`apps/web/src/app/{signin,account}`) | `test_sessions.py`; `e2e/auth.spec.ts` | Web OIDC redirect + native PKCE/secure storage (need B04 tenant); recovery at IdP |
| P04.S2.T1 Roles in API | IMPLEMENTED (identity scope) | Permission matrix (`permissions.py`), `require()` dependency, object-level checks on own profile/consents | student→admin 403; self-grant 403 | Apply to content/attempt modules as they land |
| P04.S2.T2 Staff protection | IMPLEMENTED (API) | MFA-gated permissions, audited grant/revoke, bootstrap CLI | MFA 403 test; audit assertions | Staff UI; emergency-access runbook |
| P04.S3.T1 Learning preferences | IMPLEMENTED (API + web) | `PUT /v1/me/profile` (grade, stream, five subjects, MDCAT/ECAT target, year, language, daily minutes; no ID documents); web `/onboarding` with full-mock scope note (SCOPE-01) | validation tests; onboarding E2E | Mobile onboarding screens |
| P04.S4.T2 Consent records | IMPLEMENTED (API) | Versioned consent accept/withdraw; terms/privacy only end via account closure | tests | Reviewed policy texts (legal review) |
| P11 (web Learn/Search screens, partial) | IN_PROGRESS | `apps/web` pages with loading/empty/error/not-found states | E2E | Auth, lessons, practice |

## Gates
| Gate | Status | Notes |
|---|---|---|
| G00 | NOT_READY | Early scope mostly recorded. Needs requirement trace and named input owners |
| G01 | NOT_READY | Contracts started. P01.S4 spikes not run |
| G03 | NOT_READY | Web skeleton on real structure. Native builds and reviewed owner lesson missing |
| All others | NOT_READY | — |

## Measured
- 10 sources registered (2,488 PDF pages); catalogue 122 chapters, 1,868 navigable topics; import 1.9k rows idempotent.
- API tests 40/40 (order-independent); mypy strict clean; ruff clean. Content identity tests 8/8. Web lint/typecheck/build clean; E2E 12/12 (desktop + phone).
