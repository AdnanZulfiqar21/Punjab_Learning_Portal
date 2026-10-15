# API module boundaries (P01.S1.T2, MODULES-01)

The API is one FastAPI app (`apps/api/src/portal_api`) built from modules under `modules/`. This page states what each
module owns and which way imports may go. `apps/api/tests/test_module_boundaries.py` checks the rules on the import
graph and fails a change that breaks them.

## Layers

| Layer | Members | May import at module level |
|---|---|---|
| Core | `config`, `db`, `errors`, `days`, `observability`, `budget` | other core files only |
| Foundation modules | `identity`, `audit`, `curriculum`, `notifications`, `access`, `exports`, `analytics`, `system` | core and other foundation modules |
| Feature modules | `content`, `assessment`, `written`, `support`, `help` | core, foundation and other feature modules |
| Entry points | `main` (assembles the app), `export_openapi`, `release` | anything |

| Module | Owns |
|---|---|
| identity | accounts, sessions and tokens, staff roles and scopes, permissions, MFA, learner settings |
| audit | the append-only audit trail and its redaction |
| curriculum | the catalogue: grades, subjects, books, chapters, topics, sources |
| notifications | in-app notifications and their delivery |
| access | plans, trials, entitlements, products and prices, trial devices |
| exports | data exports and their worker |
| analytics | events, funnels, learning and business reports, trial decisions, cohort economics |
| system | operations (rollouts, signals, switches), clients and versions, integrations, scanning, business overview |
| content | the studio: items, versions, review and publication, assets, lectures, imports, search, study packs |
| assessment | practice forms and attempts, mocks and sessions, scoring and corrections, notebook, plans and progress |
| written | written tests: forms, attempts, evidence, sealing, marking, rechecks, adjudication, results |
| support | help requests, learner lookup |
| help | help articles |

## Rules

1. **Core imports no module at import time.** Core files are the base everything else stands on.
2. **Only entry points import the app** (`portal_api.main`).
3. **Routers are leaves.** No module imports another module's `router` (or `review_router`); shared logic lives in the
   module's other files. For example, audit redaction lives in `audit/redaction.py` so the export worker can use it.
4. **Foundation modules don't import feature modules at import time.** When a foundation module needs a feature module
   (for example, `identity` gathering a learner's written tests for their own data export), it imports inside the function that needs it.
   That keeps the import-time structure layered and avoids cycles.
5. **No new import-time cycles.** Two exist today and are listed in the test (`audit` ↔ `identity`, `assessment` ↔
   `written`); any other fails the test. They should be removed, not added to.
6. **A new module is placed in a layer.** The test fails until it is added to `FOUNDATION` or `FEATURES` and to this
   page.

## Calls between modules

- A module calls another through its plain functions (`service.py`, `workflow.py` and the like), never through HTTP.
- Each module owns its tables; another module reads them through the owner's functions or models and writes them
  only through the owner's functions, so audit entries and invariants stay in one place.
- Background commands are declared with their budget class (`budget.process_class`, POOL-CAPS-01).
