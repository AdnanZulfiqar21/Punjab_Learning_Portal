# Contributing (P03.S1.T3)

How to run, check and change this repository. Read `CLAUDE.md` first for the project rules. The architecture notes are
`docs/architecture/modules.md`, `api-conventions.md` and `schema-and-index-policy.md`. Pinned versions are in
`docs/project/STACK.md`.

## Rules that are never bent

- **This repository is public.** The owner's textbooks in `11 Class Data/` and `12 Class Data/` are never committed
  (IMPL-01). `.gitignore` also excludes `Animated Lectures/`, OCR text (`education_knowledge/source_text/`), every
  `*.pdf` except the synthetic e2e fixtures, and `.env*`. The sources are registered by checksum only
  (`content/source_registry.json`).
- **No invented academic content.** No demo lessons, placeholder MCQs, fake marks or hard-coded success states.
  Generated lessons are drafts and need a second person's review before publication. Development fixtures say in
  their text that they are technical fixtures. Class XI and XII are never mixed.
- **Records.** Update `docs/project/` with every meaningful change (register, decisions, resume state, blockers).
  A blocker is never passing evidence.

## Local setup

Ports: API 8100, web 3100, Expo web 8190, PostgreSQL 55432. Ports 8000 and 3000 belong to another project on the owner's
machine.

```bash
docker compose -f infra/docker-compose.yml up -d        # Postgres 17 on 127.0.0.1:55432 (+ Valkey, queue and S3 emulators)
cd apps/api
uv sync
uv run alembic upgrade head                              # migrations are a separate step; the API never migrates itself
uv run portal-import-catalogue --apply                   # the real catalogue from content/ (dry run without --apply)
uv run uvicorn portal_api.main:app --host 127.0.0.1 --port 8100 --reload
```

```bash
pnpm install                                             # repository root (pnpm 10, Node 22)
pnpm --filter web dev                                    # http://localhost:3100; talks to http://127.0.0.1:8100 by default
cd apps/mobile && npx expo start --web --port 8190       # Expo web target (not device evidence)
```

Only Postgres is needed by the API and its tests. No API code talks to Valkey or the queue emulator yet; background
work is database-backed. The S3 emulator is used only with `PORTAL_EVIDENCE_STORE=s3`; the variables are in the
comments of `infra/docker-compose.yml`. API settings are `PORTAL_*` environment variables (`portal_api/config.py`);
the development defaults point at the compose services.

## Seed and reset

All commands run from `apps/api` with `uv run`.

| Command | What it does |
|---|---|
| `portal-import-catalogue [--apply]` | Upserts the catalogue and source registry by stable ID. It never deletes or publishes |
| `portal-dev-seed-staff` | Development/test only. Creates content staff fixtures with scoped roles (idempotent) |
| `portal-dev-seed-practice` | Development/test only. Creates labelled technical-fixture MCQs in one Class XI Biology chapter |
| `portal-dev-fixture-rubric-correction setup` | Development/test only. Creates the fixture for the rubric-correction journey |
| `portal-grant-role --email … --role … --reason …` | Grants a staff role from the CLI (bootstraps the first admin; the account must have signed in once) |
| `portal-help-import [DIR]` | Imports help articles as drafts |
| `python ../../content/tools/import_lessons.py --api http://127.0.0.1:8100` | Development only. Imports drafted lessons and figures through the API as a content author; publishes nothing |

The workers and scheduled jobs (`portal-written-worker`, `portal-import-worker`, `portal-expire-attempts`,
`portal-notification-worker` and the others) are listed in `pyproject.toml` `[project.scripts]` and their budget
classes in `docs/project/CAPACITY_BUDGET.md`. End-to-end tests need `portal-written-worker` and `portal-import-worker`
running.

**Reset.** `docker compose -f infra/docker-compose.yml down -v` destroys only these local volumes. Then repeat the setup
and seeds. The test database `portal_test` (created by `infra/postgres/init/`) is dropped and re-migrated by
`tests/conftest.py` at the start of every pytest session. There is nothing to reset by hand.

## Checks, exactly as CI runs them

CI is `.github/workflows/ci.yml`. Path filters decide which jobs run, and `security` always runs. Run the jobs that
match what you touched.

**`api`** (in `apps/api`; needs Postgres)
```bash
uv sync --locked
uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest
uv run alembic upgrade head && uv run alembic check          # models and migrations agree
uv run python -m portal_api.export_openapi ../../packages/contracts/openapi.json
git diff --exit-code -- ../../packages/contracts/openapi.json  # no contract drift
uv run python -m portal_api.release check                     # one head, downgrades, contract markers
uv run python -m portal_api.qualification check
uv run python -m portal_api.release manifest > /dev/null
```
pytest uses `PORTAL_TEST_DATABASE_URL` (default `…@127.0.0.1:55432/portal_test`). It refuses any database whose
name doesn't end in `_test`.

**`web`** (repository root)
```bash
pnpm install --frozen-lockfile
pnpm --filter @portal/contracts generate && git diff --exit-code -- packages/contracts/src/generated.ts
pnpm --filter web lint && pnpm --filter web typecheck && pnpm --filter web build
node apps/web/scripts/check-bundle.mjs && node apps/web/scripts/check-tokens.mjs
# API on :8100 with PORTAL_HEALTH_SAMPLE_S=0, catalogue imported, both dev seeds, both workers, import_lessons.py;
# then `pnpm start` in apps/web
pnpm --filter web exec playwright install --with-deps chromium firefox webkit
pnpm --filter web exec playwright test
```
Mobile-sized projects skip the two-device, lesson-access and staff-preview journeys unless `E2E_FULL_MATRIX=1` is set;
set it on each release candidate.

**`mobile`** (in `apps/mobile`): `pnpm typecheck`, `pnpm lint`, `pnpm test`, `npx expo config --type public`. CI
also checks that the production variant refuses to build without `PORTAL_API_ORIGIN`. `npx expo install --check`
reports drift without failing.

**`content`**: `python -m pytest content/tools -q`, then `python content/tools/build_catalogue.py --today 2026-10-07 &&
git diff --exit-code -- content/`.

**`security`**:
- `uvx pip-audit==2.9.0` on the exported runtime requirements;
- `pnpm audit --prod --audit-level=high` (reviewed exceptions in the root `package.json`);
- the SBOM tool tests (`uvx pytest==9.1.1 tools -q`);
- detect-secrets 1.5.0 against `.secrets.baseline`. A reviewed false positive is marked
  `# pragma: allowlist secret` on its line.

**`images`**: builds both Dockerfiles from the repository root and requires the API image to answer `/healthz` without
migrating.

## Code conventions

- **Python.** Ruff (line length 120; rules E, F, W, I, B, UP, S, SIM, RUF) and `ruff format`, which also cover
  `migrations/`. mypy is strict on `src`. Module import rules are enforced by `tests/test_module_boundaries.py`.
- **TypeScript.** ESLint (`eslint-config-next` for web, `expo lint` for mobile) and `tsc --noEmit`. No formatter is
  configured for TypeScript.
- **Line endings.** LF everywhere (`.gitattributes`).
- **API changes.** Follow `docs/architecture/api-conventions.md`. Changes are additive under `/v1`, errors are problem
  details, and new staff routes need a permission (AUTHZ-01 will fail otherwise).

### Migrations

```bash
cd apps/api
uv run alembic revision -m "attempt.flagged: questions a learner flagged"   # add --autogenerate to draft from the models
uv run ruff check --fix migrations && uv run ruff format migrations           # the template predates the house style
```
- The file is named `YYYYMMDD_<12-hex revision>_<slug>.py` (`alembic.ini` `file_template`).
- The docstring's first line is `<tables/columns>: <what> (<roadmap task>, <DECISION-ID>)`. Then say why the previous
  build keeps working.
- Write a real `downgrade()`.
- Expand now, contract later: dropping or renaming needs a `# contract-migration: <reason>` line and a later release
  (`docs/architecture/schema-and-index-policy.md`).
- Changing an attempt, answer, receipt, entitlement or trial table is a requalification trigger.

### Contracts

After any API schema change, run
`uv run python -m portal_api.export_openapi ../../packages/contracts/openapi.json` (in `apps/api`), then
`pnpm --filter @portal/contracts generate` (root). Commit both `openapi.json` and `src/generated.ts`. Add aliases to
`packages/contracts/src/index.ts` when the web or mobile app needs them.

## Commits and pull requests

- **Branches.** `feat/…`, `fix/…`, `content/…`, `records/…`, `docs/…`, `test/…`, cut from `main`.
- **Commit subject.** One imperative English sentence, no type prefix, with the roadmap task in parentheses when there
  is one. Example: `Bind qualification evidence to the measured release manifest (P20.S4.T4)`.
- **Commit body.** Says why. Names the decision ID (for example `QUALIFICATION-01`) and what is *not* done.
- **Merging.** PRs are merged with merge commits (`Merge pull request #N …`) on green CI of the head commit. Bring a
  branch up to date by merging `main` into it; don't rebase or force-push.
- **Record PRs.** Updates to `docs/project/` records often go in a separate `records/…` PR. Parallel PRs that add
  DECISIONS rows conflict, and GitHub runs no CI on a conflicted PR.

## Debugging

- **`GET /readyz`** answers 503 `database: unreachable` when Postgres is down, on another port, or has never been
  migrated (no `alembic_version` table yet). In each case check the port, then run `uv run alembic upgrade head`.
  `/healthz` never touches the database.
- **Port taken or Postgres unreachable on Windows:** reserved port ranges move after a reboot. Check
  `netsh interface ipv4 show excludedportrange protocol=tcp` and set `PORTAL_DATABASE_URL` /
  `PORTAL_TEST_DATABASE_URL` to the port in use. A stopped background task can leave uvicorn or Expo holding a port;
  find it with `Get-NetTCPConnection -LocalPort <port>`.
- **Follow a request.** Every response has `X-Correlation-ID`, every error body has `correlation_id`, and the API logs
  one `request` line with it. Send your own `X-Correlation-ID` to find a request in the logs, audit rows and jobs.
- **What a 503 means:**
  - `SERVICE_BUSY`: the connection pool stayed exhausted for 5 s.
  - `SERVICE_UNAVAILABLE`, with the log line `database unavailable: QueryCanceled`: a query passed the 5 s
    `statement_timeout`. Look for a missing index.
  - `WRITTEN_PAUSED`: the workload guard paused written tests. Locally, run the API with `PORTAL_HEALTH_SAMPLE_S=0`,
    as CI's web job does.
- **Interactive API docs** are at `http://127.0.0.1:8100/docs` (development and test roles only).
- **pytest.** One session per test database: the second one stops with a `UsageError` (advisory lock). Use another
  `*_test` name in `PORTAL_TEST_DATABASE_URL`, which is created if missing. Read pytest's real exit code; piping
  through `tail` hides it.
- **426 `UPDATE_REQUIRED`** means the request sent `X-Portal-Platform` / `X-Portal-App-Version` below an enforced
  minimum (`GET /v1/clients/policy`).
- **Mobile.** `pnpm doctor` runs pnpm's own built-in command. Use `pnpm run doctor` or `npx expo install --check`.
  Run Expo without `CI=1`, otherwise files aren't watched.
- **Timing.** `curl localhost` adds about 250 ms (IPv6 fallback); use `127.0.0.1` for timings.
