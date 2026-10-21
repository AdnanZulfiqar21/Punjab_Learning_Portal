# API conventions (P01.S3.T1)

One FastAPI app (`apps/api/src/portal_api/main.py`) serves the student web, the Android and iOS apps and the staff
admin. The published contract is `packages/contracts/openapi.json` (273 paths, 303 operations). This page describes
what the code does. Inconsistencies are listed at the end.

## Paths and versioning

- Every contract path starts with `/v1` (`APIRouter(prefix="/v1…")` in each module). Outside it are only `/healthz`
  and `/readyz` (`include_in_schema=False`), `/docs` (development and test roles only), `/openapi.json` (served in
  every role) and the development sign-in routes under `/v1/dev-auth`, which are mounted only when
  `dev_auth_enabled` and left out of the schema.
- Prefixes show the audience: `/v1/me/…` for the signed-in learner, `/v1/studio/…` for content staff,
  `/v1/staff/…`, `/v1/admin/…` and `/v1/ops/…` for operators. Everything else is learner or public.
- **Breaking changes are not made inside `/v1`; changes are additive.** There is no `/v2` and no deprecation mechanism
  (no `deprecated=True`, no `Deprecation` or `Sunset` headers). Compatibility is enforced by
  `tests/test_upgrade_compatibility.py` (MIGRATION-COMPAT-01). `tests/compat/mobile_2026-10-10.json` holds the 57
  operations and 105 schemas that the mobile build at commit `362db5b` uses. The current API must keep each operation,
  add no required input (body field or query parameter), keep every field the app reads with the same type, never
  send null or an unseen enum value where it didn't before, and still accept the old request bodies. A mutation test
  proves the check catches each of these. Move the baseline at each release (`docs/runbooks/release-rollback.md`).
- New behaviour is opt-in for older clients. For example, `GET /v1/search?lessons=true` (SEARCH-01) is sent only by
  newer builds. Omitted fields keep stored values: `PATCH /v1/me/settings` changes only the fields it names, and a
  mapping save without `regions`, `order` or `confirmed` keeps the current ones (`written/service.py`
  `update_manifest`).
- **Retiring old apps (CLIENTS-01, `modules/system/clients.py`).** Operators set a minimum app version per platform.
  It is announced first and enforced no sooner than 14 days later, never inside a mock window. `GET /v1/clients/policy`
  answers `ok`, `update_soon` or `update_required`. Once the minimum is enforced, a request carrying `X-Portal-Platform`
  and `X-Portal-App-Version` below it gets 426 `UPDATE_REQUIRED`. The web app is deployed with the API and has no
  minimum.

## Errors: RFC 9457 problem details

Every `AppError` (`portal_api/errors.py`) and request-validation failure is answered as
`application/problem+json`:

| Member | Value |
|---|---|
| `type` | `https://errors.portal.invalid/<code in lowercase>` (not resolvable) |
| `title` | The machine code, for example `CONFLICT` |
| `status` | The HTTP status |
| `detail` | One sentence fit to show the user |
| `correlation_id` | Same as the `X-Correlation-ID` response header |
| extras | Keyword arguments to the error are merged at top level and never override the members above |

Common extras:
- `code_reason`: a finer machine reason, used at 148 raise sites, for example `KEY_REUSED`, `NOT_IN_PLAN` or
  `FEATURE_NOT_AVAILABLE`;
- `errors`: a list (`[{loc, msg}]` for validation);
- `current`: the latest server state on a 409;
- state fields such as `state`, `availability` and `attempt_status`.

The TypeScript `Problem` type is hand-written in `packages/contracts/src/index.ts`.

| Status | `title` codes in use |
|---|---|
| 401 | `UNAUTHENTICATED`, always with `WWW-Authenticate: Bearer realm="portal"` |
| 403 | `FORBIDDEN`, `REAUTH_REQUIRED`, `ACCESS_REQUIRED` (`code_reason` `NOT_IN_PLAN` for a plan that doesn't cover the scope), `ALLOWANCE_EXHAUSTED`, `DEVICE_AUTHORIZATION_REQUIRED`, `WRITTEN_PILOT_ONLY` |
| 404 / 410 | `NOT_FOUND` / `GONE` |
| 409 | `CONFLICT`, `ATTEMPT_FINALISED` |
| 413 | `PAYLOAD_TOO_LARGE` |
| 422 | `VALIDATION_FAILED` (request schema; `errors: [{loc, msg}]`), `RULE_FAILED` (a domain rule) |
| 426 | `UPDATE_REQUIRED` |
| 429 | `RATE_LIMITED` (per-account limits) |
| 503 | `SERVICE_UNAVAILABLE`, `STORAGE_UNAVAILABLE`, `SCANNER_UNAVAILABLE`, `WRITTEN_PAUSED` (all with `Retry-After`); `SERVICE_BUSY` (pool timeout, `Retry-After: 5`; evidence workers busy, `Retry-After: 10`); `FEATURE_DISABLED` |

A database `OperationalError` becomes 503 `SERVICE_UNAVAILABLE`. That includes a query cancelled by
`statement_timeout`, which is logged as `database unavailable: QueryCanceled …`.

## Authentication and authorisation

- **Bearer tokens only** (`identity/deps.py`). `Authorization: Bearer <token>` carries one of two things:
  - an opaque, revocable application session token (prefix `pls_`; only its SHA-256 is stored; the web keeps it in an
    HTTP-only cookie, apps keep it in OS secure storage);
  - a JWT from the OIDC provider or the development issuer, checked for signature (JWKS), issuer, audience and expiry
    (`identity/tokens.py`). The first verified JWT creates the account.

  Missing or invalid credentials give 401. An inactive account gets 403. An unreachable identity provider gives 503
  with `code_reason` `IDENTITY_UNAVAILABLE`. Public routes that read a caller when one is present use
  `OptionalPrincipal`; invalid credentials there are still 401.
- **Roles and permissions** (`identity/permissions.py`). Every account is a `student`. Staff roles are granted in
  `staff_role_grant`, optionally scoped to grades and subjects. `require(Permission.x)` gives 403 without the
  permission, and 403 when the permission is in `MFA_REQUIRED` and the session has no MFA (publish, quarantine,
  adjudicate, finance, operate, manage roles, audit, source rights, grants, trial review, learner lookup, exam
  profiles, voices, catalogue, business overview). Exporting or deleting your own account needs a sign-in within 15
  minutes (403 `REAUTH_REQUIRED`).
- **Checks run before the lookup.** `tests/test_authorization_matrix.py` (AUTHZ-01) checks three things:
  - the unauthenticated surface equals a reviewed allowlist;
  - every other route answers an anonymous call with 401;
  - a learner gets exactly 403 from every `/v1/studio`, `/v1/staff`, `/v1/ops` and `/v1/admin` route, so authorisation
    runs before object lookup or body validation.
- **Out of scope looks like 404.** Another learner's form, attempt, result or export, and staff objects outside the
  caller's grade or subject scope, answer 404, not 403. Examples: `assessment/attempts.py` `_lock`,
  `content/router.py` `_scoped_item`, `content/assets.py`, `content/lectures.py`, `written/review.py`,
  `exports/service.py`.

## Lists and pagination

There is no single scheme. These are the styles in use:

| Style | Routes | Parameters → response |
|---|---|---|
| Keyset cursor | `GET /v1/admin/audit` | `before` (opaque), `limit` 1–200 (50) → `{events, next_before}`; `next_before` is null at the end |
| Offset | `GET /v1/me/notifications`; `GET /v1/studio/written/adjudications`; `…/adjudications/{id}/attempts` | `offset` ≥ 0, `limit` 1–100 (30 / 50 / 25) → `{items, unread}`, a bare list, `{total, items}` |
| First N only | `/v1/admin/entitlements` (1–500, 200), `/v1/studio/queue` (1–200, 100), `/v1/search` (1–50, 20), `/v1/help/articles` (1–50, 30), `/v1/ops/notifications/dead-letters` (1–200, 50) | `limit` → list; you can't page past it |
| Fixed server cap | for example `/v1/studio/lectures` (200), `/v1/studio/concepts` (500), `/v1/exports` (50 newest), `/v1/studio/syllabus-notices` (200) | no parameter |

Bounds are declared with `Query(ge=…, le=…)`, so an out-of-range value gets 422 `VALIDATION_FAILED`. 46 `GET`
routes return an array and take no `limit`. Most of them are naturally small (a learner's own sessions or devices);
the rest rely on a fixed cap in the service.

## Idempotency and concurrency

- **Creates take a key.** These creates require an `Idempotency-Key` header (8–80 characters): practice forms, mocks,
  review tests, written forms and linked written forms. Written rescans declare the header optional, but a request
  without it gets 422 `RULE_FAILED` with `code_reason` `KEY_REQUIRED`. The key is stored with a hash of the request. A retry with the same key and the same request
  returns the original result; the same key with a different request gives 409. The MCQ submit takes
  `idempotency_key` in its body.
- **Answer saves are operations, not overwrites** (§10.5, `assessment/attempts.py`). Each op carries a client `op_id`
  and a per-question `revision`. An exact replay returns the stored result with `replay: true`. An older revision is
  `stale`, and a write after finalisation is `finalised`. These come back as per-op dispositions in a 200, not as
  errors. Submission writes exactly one receipt; `same_request: false` means another request or expiry finalised the
  attempt.
- **Optimistic concurrency gives 409 with `current`.** A client sends the revision it started from. On a mismatch the
  API answers 409 `CONFLICT` with the latest state in `current`. This covers studio drafts (`revision`,
  `content/workflow.py`), written answer mapping and sealing (`expected_revision`, `written/service.py`) and study
  notes (`base_revision`, `content/study.py`; resending identical text is not a conflict).
- **Starting a practice attempt is idempotent.** A second start of the same form returns the existing attempt
  (`assessment/attempts.py` `start`).

## Caching and response headers

- Every response defaults to `Cache-Control: private, no-store` (the `security_headers` middleware in `main.py`,
  ISOLATION-01). Routes opt in to sharing explicitly:
  - `public, max-age=60, stale-while-revalidate=300`: the catalogue, discovery, and anonymous chapter lessons (with
    `Vary: Authorization`);
  - `public, max-age=60`: products and help articles;
  - `public, max-age=30`: `/v1/status`;
  - `public, max-age=300`: client policy;
  - `public` or `private, max-age=3600`: immutable asset versions (`public` only for preview-tier lesson files).

  `tests/test_privacy_isolation.py` sweeps every non-public `GET` without path parameters from the live OpenAPI
  document and fails on a cacheable personal response.
- Every response also carries `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` and
  `Referrer-Policy: no-referrer`. Every path except `/docs` and `/openapi.json` also gets
  `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` (`tests/test_security_headers.py`).
- `X-Correlation-ID` is accepted when valid, otherwise generated, and returned on every response
  (`observability.py`). CORS allows `Idempotency-Key`, `X-Portal-Client`, `X-Portal-Install`, `X-Portal-Platform`
  and `X-Portal-App-Version`.

## The contract and drift checks

1. After changing an API schema, run `uv run python -m portal_api.export_openapi ../../packages/contracts/openapi.json`
   (in `apps/api`) and `pnpm --filter @portal/contracts generate` (openapi-typescript → `src/generated.ts`). Add stable
   aliases to `packages/contracts/src/index.ts` when a client needs them.
2. CI's `api` job re-exports the document and runs `git diff --exit-code -- packages/contracts/openapi.json`. The `web`
   job regenerates the types and runs `git diff --exit-code -- packages/contracts/src/generated.ts`. Either fails on
   drift. The `web` job's path filter includes `apps/api/`.
3. `python -m portal_api.release manifest` records the contract's SHA-256 (`openapi_sha256`) for each build.

## Known gaps

- Unknown paths and wrong methods return FastAPI's `{"detail": "Not Found"}` and `{"detail": "Method Not Allowed"}` as
  `application/json`, not problem details. There is no handler for unexpected exceptions, so they give a plain 500.
- The OpenAPI document doesn't match the errors actually returned. It lists FastAPI's default 422 `HTTPValidationError
  {detail: [...]}` on 252 operations, while the API returns problem details with `errors`. No other error response and
  no `securitySchemes` (bearer auth) are declared.
- A missing MFA session and a missing permission are both 403 `FORBIDDEN`; only `detail` differs.
- No `Retry-After` header on 429 `RATE_LIMITED`, on 503 `FEATURE_DISABLED`, or on 503 from `OperationalError`.
- Studio actions on an out-of-scope item answer 403 (`content/workflow.py` `_require_scoped`), while reads of the same
  item answer 404.
- Pagination has four styles and three response envelopes. `/v1/studio/lectures` and `/v1/studio/syllabus-notices`
  apply `LIMIT 200` before filtering by the caller's scope, so a scoped reviewer can miss their own rows once the table
  passes 200.
- Concurrency tokens have three names (`revision`, `expected_revision`, `base_revision`). Idempotency keys are a header
  on creates but a body field on MCQ submit. A reused key carries `code_reason` `KEY_REUSED` only on linked written
  forms and rescans; practice, mock, review and written form creation answer a bare 409 `CONFLICT`.
- There is no deprecation signal. The compatibility test covers only the oldest mobile build's operations, not staff
  routes (the web deploys with the API).
- DECISIONS ENTITLEMENT-SCOPE-01 says "403 `NOT_IN_PLAN`". The code answers 403 `ACCESS_REQUIRED` with `code_reason`
  `NOT_IN_PLAN`.
