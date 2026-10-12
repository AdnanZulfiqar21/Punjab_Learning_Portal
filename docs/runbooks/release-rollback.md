# Rolling back a release (P19.S3.T1, MIGRATION-COMPAT-01)

**Status:** the strategy is enforced by tests; running it for real waits on a deployment (B03).

## The rule

Rolling back means running the **previous build against the current database**. A release never runs
`alembic downgrade` on a database that holds learner data. Purchases, attempts, written scripts, trial claims and
everything else written after the upgrade stay where they are.

This only works because every migration keeps the previous build working (expand first, contract later; RELEASE-01):

- no table or column the previous build uses is dropped, renamed or retyped;
- anything added to an existing table is nullable or has a default, so the previous build's inserts still succeed;
- no new unique or check rule on an existing table that the previous build could break (a widened list of allowed
  values is fine);
- a column is dropped only in a later release, with a `# contract-migration:` marker explaining why no running build
  needs it.

## Checks that hold it

| Check | Where |
|---|---|
| Migration rules (one head, every migration reversible in development, contract marker on destructive changes) | `python -m portal_api.release check` (CI) |
| The previous build's schema (`e8b2d6f4a193`, build `362db5b`) still fits the current one | `tests/test_upgrade_compatibility.py::test_the_previous_build_runs_on_the_current_schema` |
| A populated earlier database upgrades with every row intact, and the current build serves its learners | `test_a_populated_earlier_schema_upgrades_without_loss` |
| The oldest supported mobile build still gets every field it reads | `test_the_oldest_supported_mobile_client_still_works` |

When a release ships, move the baseline to it: regenerate `tests/compat/mobile_<date>.json` from that commit's mobile
app and `tests/compat/baseline_<date>.sql.gz` from that build's own test journeys (see the test module's docstring).

## Steps (once deployed)

1. **Prefer switching the feature off.** If a new feature is the problem, lower its rollout to 0% on
   **Admin → Service overview → Feature rollouts**, with a reason (ROLLOUT-01). The code stays; learners stop seeing it.
2. Otherwise redeploy the previous build's image. Do **not** run `alembic downgrade`; the database stays at the newer
   revision, which the previous build can use.
3. Record the rollback in the release record with the release manifest of both builds (`python -m portal_api.release
   manifest`).
4. Fix forward. The next release starts from the current database revision.

`alembic downgrade` remains available for development databases and for the migration round-trip check only.
