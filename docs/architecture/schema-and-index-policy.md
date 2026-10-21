# Schema, migration and index policy (P01.S2.T2)

One PostgreSQL 17 database. Every table is in the `public` schema. Each module declares its own tables as SQLAlchemy 2
models on `portal_api.db.Base` (ownership: `docs/architecture/modules.md`). The Alembic chain lives in
`apps/api/migrations/versions/`. This page describes what the schema does today and the rules CI enforces. Anything
not yet exercised is marked **Policy (proposed)**. Counts come from the model metadata at commit `764319e2`
(108 tables).

## Naming

| Thing | What the code does | Example |
|---|---|---|
| Tables | Singular `snake_case`. Some names carry a module prefix (`written_*`, `content_*`, `trial_*`, `notification_*`) | `attempt`, `answer_op`, `written_review_case` |
| Columns | `snake_case`. Foreign keys are named `<thing>_id`, and actor columns are named `<verb>_by` | `owner_id`, `published_by` |
| Check constraints | Always named (110 of 110). 98 are named `<table>_<rule>`. The other 12 use a shortened prefix. There is no `ck_` prefix | `practice_form_count`, `written_case_status` |
| Unique constraints | 38 are named `uq_<table>[_purpose]`. 23 are unnamed and get PostgreSQL's default `<table>_<cols>_key` | `uq_answer_op`, `uq_attempt_form_user` |
| Indexes | `ix_<table>_<cols or purpose>`. `index=True` gives SQLAlchemy's `ix_<table>_<column>`. Unique indexes are named `uq_…` | `ix_attempt_active_cutoff`, `uq_commerce_terms_published` |
| Foreign key constraints | Unnamed (PostgreSQL default `<table>_<col>_fkey`) | |

`Base` has no `MetaData(naming_convention=…)`, so a name exists only where the code writes it.

## Keys

- **UUID primary keys.** 93 tables have a single `id UUID` key and 85 of them use `default=uuid.uuid4`. The ID is
  generated in Python; there is no database default, so a raw SQL insert must supply it (as `identity/deps.py` does).
- **Stable derived IDs.** Catalogue rows (`region`, `grade`, `subject`, `source_document`, `book_edition`, `chapter`,
  `topic`) have uuid5 IDs from `content/tools/build_catalogue.py` and `modules/curriculum/importer.py`, so a re-import
  upserts the same rows. `analytics_event.id` is `uuid5(name:key)`, so a repeated event is one row.
- **Other shapes.** Four one-to-one tables are keyed by `user_id` (`student_profile`, `dev_credential`,
  `study_settings`, `notification_preference`). Six tables have composite keys, for example `attempt_answer
  (attempt_id, position)`. Four use natural keys (`feature_switch.key`, `feature_rollout.key`, `push_token.token`,
  `workload_guard.name`) and one uses an integer identity (`health_sample.id`).
- **Idempotency is stored, not assumed.** A client key is persisted with a uniqueness rule, for example
  `uq_practice_form_idempotency (owner_id, idempotency_key)` plus a `request_hash`, and `uq_answer_op (attempt_id,
  op_id)` (see `api-conventions.md`).

## Column types

- **Timestamps.** All 199 `DateTime` columns are `timestamptz` (`DateTime(timezone=True)`). 49 of the 51 `created_at`
  columns default to `now()` on the server, which is the transaction start time. Times that decide an outcome (attempt
  admission, deadlines, entitlements, trial devices, adjudications) come from the database clock via
  `select clock_timestamp()` read after taking the row lock (`db_now` in `assessment/attempts.py`,
  `access/service.py`, `written/service.py`). `updated_at` exists on 21 tables. Application code maintains it; only
  2 use `onupdate=func.now()`.
- **States and kinds.** These are `String(n)` with a `CheckConstraint` listing the allowed values, for example
  `attempt_status: status in ('active','finalised','void')`. No PostgreSQL `ENUM` type is used, so a new value is a
  check change. Widening a check is backward-compatible; narrowing one is not (see Migrations).
- **Money.** Prices are `amount_minor BigInteger` plus `currency String(3)` (`product_price`). `Numeric` appears only
  in `cost_rate.amount (14,4)` and `score_version.percentage (6,2)`.
- **JSONB.** There are 93 columns, 85 of them `NOT NULL`. They hold frozen snapshots (`practice_form.scope`,
  `form_item.option_order`, `attempt.flagged`), versioned bodies (`content_version.body`, validated by the block
  registry in `content/blocks.py`), role-grant scope, audit `details` (redacted on read) and analytics `properties`.
  The application validates their shape; there are no database checks on JSONB content. A JSONB column added to an
  existing table is nullable or gets a server default (`'[]'::jsonb`, `'{}'::jsonb`), so older builds' inserts keep
  working.
  The only index over JSONB content is the lesson full-text expression index (see Indexes).
- **Strings.** Codes and keys use bounded `String(n)`. Free text uses `Text`.

## Constraints and foreign keys

- **Foreign keys.** There are 228. 219 are `ON DELETE RESTRICT`. History is kept: learner deletion requests are routed to
  support and nothing is erased automatically (`identity/privacy.py`, B15). 8 are `CASCADE`, and they cover only
  rows that belong wholly to their parent: a user's profile, consent records, sessions, study settings and dev
  credential, a concept's links, and an import batch's rows. One is `SET NULL` (`attempt.holder_session_id`).
- **Invariants live in the database where they can.** Uniqueness rules and partial unique indexes enforce "one" rules:
  one attempt per form and learner, one published commerce terms row, one open regrade job per correction, and so on.
  Check constraints enforce ranges and states.
- **Append-only by trigger.** `audit_event` refuses `UPDATE` and `DELETE` through `audit_event_no_change`
  (migration `e8c1b7d4a206`). Other "append-only" tables (prices, cost rates, score versions) are append-only by
  application code only.

## Indexes

What the code does:

- **Declared on the model and created by the same change's migration.** CI's `alembic upgrade head && alembic check`
  fails when models and migrations disagree, so an index exists only when both have it.
- **Added for a query the code runs.** Lookup foreign keys are `index=True` (owner, user, attempt, form). Worker queues
  use partial indexes, for example `ix_attempt_active_cutoff … WHERE status = 'active'` for the expiry worker and
  `ix_notification_delivery_due … WHERE status = 'queued'`. In total there are 123 indexes: 105 `ix_`, 18 unique, 21 partial.
- **Search.** `pg_trgm` GIN indexes cover `chapter.title`, `topic.title` and `search_alias.normalized`. A GIN
  expression index covers `to_tsvector('english', lesson_search_text(body))`; the function is defined in migration
  `f6a1c3e8b204`. Help search computes `to_tsvector('simple', …)` at query time without an index.
- **Bounded queries.** Each pooled connection runs with `statement_timeout` = `PORTAL_DB_STATEMENT_TIMEOUT_MS` (5000 ms,
  `db.py`). A slow query fails rather than holding the pool. Studio lists apply scope in SQL before `LIMIT`
  (`content/router.py`). `tests/test_report_query_counts.py` pins the learner reports to a fixed number of queries
  whatever the history length, and `tests/test_large_history.py` times them on a large cloned history (local evidence
  only).
- **Not indexed.** 128 of the 228 foreign-key columns don't lead any index, unique constraint or primary key. Most are
  actor columns (`*_by`) and version pins that are never filtered on. With `RESTRICT`, deleting a parent row then
  scans those child tables. That is acceptable while parents aren't deleted; index such a column when a query starts
  filtering on it.

**Policy (proposed).**
1. Add an index in the same PR as the query that needs it, named `ix_<table>_<purpose>`.
2. Prefer a partial index for queue scans and for "only one active" rules.
3. On a table that already holds learner data, create indexes `CONCURRENTLY` (a non-transactional migration) once
   deployments exist (B03). Today every index is created inside the migration transaction.

## Migrations

| Rule | Enforced by |
|---|---|
| Exactly one head | `python -m portal_api.release check` (CI `api` job) |
| Every migration has a `downgrade()` | same |
| Expand/contract: in revisions after `GRANDFATHERED_THROUGH` (revision `e8b2d6f4a193`, 2026-10-10, before any deployment), an `upgrade()` containing `op.drop_table(`, `op.drop_column(`, `op.rename_table(` or `new_column_name=` needs a `# contract-migration: <why the running code no longer needs it>` line | same (`release.DESTRUCTIVE`, `release.MARKER`) |
| The previous build still runs on the current schema: nothing it knows is dropped or retyped, new columns on existing tables are nullable or defaulted, and there is no new unique rule or narrowed check | `tests/test_upgrade_compatibility.py` against the baseline schema `e8b2d6f4a193` (MIGRATION-COMPAT-01) |
| A populated baseline database upgrades with every row intact | same file, `baseline_2026-10-10.sql.gz` |
| Models and migrations agree | `alembic check` in CI. Columns retired from the code but not yet dropped are listed in `release.RETIRING_COLUMNS` and ignored (`migrations/env.py`) |

- **Separate release step, never at startup.** A release runs `alembic upgrade head` before starting the new code
  (`migrations/env.py`, `apps/api/Dockerfile`). CI's `images` job starts the API image and requires `/healthz` to
  answer without migrating. `/readyz` answers 503 when no migration is recorded. It reports `unreachable` when the
  `alembic_version` table doesn't exist yet and `not migrated` when the table is empty. It doesn't require the build's
  own head, because the previous build must run on a newer schema.
- **Rollback** means running the previous build against the current schema. `alembic downgrade` is never run on data
  (`docs/runbooks/release-rollback.md`). Downgrades exist for development.
- **Contract step.** Retire the column in code first (add it to `RETIRING_COLUMNS` and give it a server default if
  inserts used it, as `b5d2e8a4c719` did). Drop it in a later release with the marker. No migration carries a marker
  yet. `student_profile.preferences` is waiting for its drop.
- **File names** come from `alembic.ini`'s `file_template`: `YYYYMMDD_<12-hex revision>_<slug>.py`. Order is the
  `down_revision` chain, not the file name. The docstring's first line names the tables or columns, then the roadmap
  task and decision ID, for example `attempt.flagged: questions a learner flagged … (P11.S3.T2, FLAGS-01)`. About half
  of the post-baseline migrations also say why the previous build keeps working (as `3b7e2a9c4d51` does); new ones
  should.

## Large tables and partitioning

Nothing is partitioned. The tables that grow with use are:
- `answer_op`: one row per admitted answer save;
- `attempt_answer`, `form_item`, `score_version` and `submission_receipt`;
- `audit_event`: append-only;
- `analytics_event`, `notification`, `notification_delivery`;
- the written evidence tables.

No table has a foreign key into `answer_op`, `audit_event` or `analytics_event`, so they can be partitioned later
without changing referencing tables.

**Indicative numbers only (VOLUME-01, one laptop, not a qualification run).** 10,000 accounts × 3 tests × 8 questions
× 3 revisions gave 720,000 answer revisions and 30,000 tests, generated in 125 s, in a 387 MB database. That is roughly
0.5 KB per answer revision with everything else included. The progress report took 305 ms on first read and 29 ms
after; the dashboard took 251 ms. One generator run is capped at 10,000,000 revisions, about 5 GB at that rate (an
extrapolation, not a measurement).

**Policy (proposed; pin numbers after the P20 load runs on the B03 hosting):**
1. Partition on measured evidence, never on row count alone. Do it when the baseline or burst scenarios on the target
   database show answer-save or submit latency, index maintenance or autovacuum lag growing with table size, or when a
   table and its indexes are projected to exceed the database server's memory within the retention period.
2. Or partition when retention (P01.S2.T3, B15) needs rows removed by age in bulk. Time-range partitions turn expiry into
   a partition drop. `audit_event` and `analytics_event` are the likely first cases (time-ordered, queried by time).
3. PostgreSQL requires the partition key in every primary key and unique constraint. For `answer_op` that changes
   `id` and `uq_answer_op`, so plan it as an expand/contract migration pair.
4. Partitioning an attempt, answer, receipt, entitlement or trial table is a requalification trigger (next section).

## Schema changes that require requalification

`portal_api/qualification.py` (QUALIFICATION-01) binds capacity, security and device claims to a measured build.
`python -m portal_api.qualification impact` lists the records that a change since that build invalidates.

| Trigger (`TRIGGERS`) | Fires when | Retests |
|---|---|---|
| `attempt_schema` | A changed file in `apps/api/migrations/versions/` has, inside `upgrade()`, a quoted identifier containing `attempt`, `answer`, `receipt`, `entitlement` or `trial` (`PROTECTED_TABLE`). This covers `attempt`, `answer_op`, `attempt_answer`, `submission_receipt`, `entitlement`, the `trial_*` tables, `written_attempt` and `written_receipt`, plus any column, constraint or index whose name contains those words | persistence failure suite (P10.S4), burst load (P20.S2.T2) |
| `infrastructure` | `infra/`, a Dockerfile, `db.py` or `budget.py` changes, or the manifest's `connection_budget` differs | connection budget, baseline load, burst load |
| `content_growth` | A course's live items more than double, or a new course goes live | query-plan review and catalogue/search scenarios |

Every schema change ships as a migration (CI's `alembic check`), so the migration file is where `attempt_schema`
looks. No qualification record exists yet (`docs/project/qualification/`), so `impact` reports that no claim is
evidenced.

## Known gaps

- No naming convention on `MetaData`: 23 unique constraints and every foreign key carry generated names, and check-constraint
  prefixes vary.
- Nine state or kind columns have no check constraint: `trial_grant.status`, `practice_form.kind`,
  `content_import_batch.kind`, `source_document.status`, `import_batch.kind`, `import_batch.status`, `export_job.kind`,
  `service_incident_update.status` and `written_auto_assessment.status`.
- Two clocks: 19 API files read `clock_timestamp()` from the database, while 11 use `datetime.now(UTC)` (content
  workflow and imports, identity sessions, `last_seen_at`).
- `release check` misses some destructive changes. It doesn't detect `drop_constraint`, column type or nullability
  changes, or raw `op.execute("DROP …")`, although `release.py`'s docstring says constraint drops need the marker.
  Retyping and narrowed checks are caught only by the compatibility test, against the baseline schema.
- Migrations run with no `lock_timeout` or `statement_timeout`. The `db.py` listener isn't used by `migrations/env.py`,
  and no index is created `CONCURRENTLY`.
- No query-plan (`EXPLAIN`) check exists. The `catalogue_search` retest is defined but has never been run.
- `attempt_schema` detection is lexical. It fires on a new table that merely has an `attempt_id` column (for example
  `3b7e2a9c4d51`). It misses raw SQL in `op.execute(...)`, because the table name isn't a whole quoted literal there.
- Partition thresholds are unpinned until P20 measurements on real hosting (B03).
- `/readyz` reports a never-migrated database (no `alembic_version` table) as `unreachable`; the `not migrated` branch
  fires only when the table exists but is empty.
