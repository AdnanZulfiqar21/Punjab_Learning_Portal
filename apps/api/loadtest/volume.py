"""Realistic data volume for load qualification (roadmap P20.S1.T1; VOLUME-01).

    uv run python -m loadtest.volume --database-url postgresql+psycopg://.../portal_load \
        --accounts 100000 --attempts 3 --questions 10 --revisions 3 --grade 11 --subject biology --report volume.json

Fills a **dedicated** load database with technical accounts and their finished practice histories, so load
scenarios (P20.S1.T2) run against a realistic database size instead of an empty one. The rows are generated
inside PostgreSQL (`generate_series`), in batches, and follow the same shapes the application writes:

* technical accounts (`load-vol-<run>-<n>@example.invalid`) under the development identity issuer, so every report
  counts them as test accounts and never as learners;
* one practice form per attempt with frozen items drawn from the **published** questions already in that database;
* finalised attempts with an answer-operation ledger of `--revisions` revisions per question (the last one is the
  saved answer), a submission receipt with the real ledger hash, and score version 1.

Budgets (roadmap §20.S1.T1): at most 100,000 accounts and 10,000,000 answer revisions per run.

The report states the **actual question volume** used: only questions already published in that database (in
development, the labelled technical fixtures from `portal-dev-seed-practice`). Generated histories exercise storage
and query shapes; they say nothing about academic coverage. No purchase events are generated: there is no payment
provider sandbox yet (B06).

**Safety:** the database name must end in `_load` (or be named with `--allow-database`), and a production runtime
role is always refused. Nothing is deleted; each run is tagged with its own `--run` id.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

MAX_ACCOUNTS = 100_000
MAX_REVISIONS = 10_000_000
BATCH_ACCOUNTS = 2_000
OPTIONS = ("o1", "o2", "o3", "o4")


@dataclass(frozen=True)
class Plan:
    accounts: int
    attempts: int  # finished practice tests per account
    questions: int  # questions per test
    revisions: int  # answer revisions per question (the last one is saved)
    grade: int
    subject: str
    run: str

    @property
    def answer_revisions(self) -> int:
        return self.accounts * self.attempts * self.questions * self.revisions


class Refused(Exception):
    pass


def check_plan(plan: Plan) -> None:
    if not 1 <= plan.accounts <= MAX_ACCOUNTS:
        raise Refused(f"Accounts must be between 1 and {MAX_ACCOUNTS:,}.")
    if min(plan.attempts, plan.questions, plan.revisions) < 1:
        raise Refused("Attempts, questions and revisions must each be at least 1.")
    if plan.questions > 200:
        raise Refused("A practice test has at most 200 questions.")
    if plan.answer_revisions > MAX_REVISIONS:
        raise Refused(f"{plan.answer_revisions:,} answer revisions is over the {MAX_REVISIONS:,} budget.")


def check_target(engine: Engine, allow_database: str | None) -> str:
    """The database must be a dedicated load database, never production."""
    from portal_api.config import Role, get_settings

    if get_settings().role is Role.production:
        raise Refused("Refusing to generate load data from a production runtime.")
    name = str(engine.url.database or "")
    if not (name.endswith("_load") or (allow_database is not None and name == allow_database)):
        raise Refused(f"Database {name!r} isn't a dedicated load database (its name must end in _load).")
    return name


def question_pool(conn: Connection, grade: int, subject: str) -> list[dict[str, Any]]:
    """Published, live multiple-choice questions of one class and subject: one version per question family."""
    rows = conn.execute(
        text(
            """
            select distinct on (coalesce(i.family_id, i.id))
                   i.id as item_id, coalesce(i.family_id, i.id) as family_id, v.id as version_id,
                   v.body->>'correct_option_id' as key,
                   (select jsonb_agg(o->>'id') from jsonb_array_elements(v.body->'options') o) as options
            from content_item i
            join content_version v on v.id = i.published_version_id
            join chapter c on c.id = i.chapter_id
            join book_edition b on b.id = c.book_id
            join grade g on g.id = b.grade_id
            join subject s on s.id = b.subject_id
            where i.kind = 'mcq' and i.availability = 'live' and g.number = :grade and s.code = :subject
            order by coalesce(i.family_id, i.id), i.id
            """
        ),
        {"grade": grade, "subject": subject},
    ).mappings()
    return [dict(r) for r in rows]


EMPTY_ADJUDICATIONS = hashlib.sha256(json.dumps([]).encode()).hexdigest()

# One batch of accounts and everything they did, generated inside PostgreSQL. Account numbers run from :first to
# :last; each account finishes :attempts tests of :questions questions with :revisions answer revisions each.
BATCH_SQL = [
    """
    create temporary table load_users on commit drop as
    select gen_random_uuid() as id, n
    from generate_series(cast(:first as int), cast(:last as int)) n
    """,
    """
    insert into app_user (id, issuer, subject, email, status, created_at, last_seen_at)
    select id, :issuer, 'load-' || :run || '-' || n, 'load-vol-' || :run || '-' || n || '@example.invalid', 'active',
           now() - interval '60 days' * random(), now() - interval '7 days' * random()
    from load_users
    """,
    """
    create temporary table load_forms on commit drop as
    select gen_random_uuid() as form_id, gen_random_uuid() as attempt_id, u.id as user_id, u.n, a,
           (u.n * :attempts + a) as seq,
           now() - interval '30 days' * random() as started_at
    from load_users u cross join generate_series(1, cast(:attempts as int)) a
    """,
    """
    insert into practice_form (id, owner_id, idempotency_key, request_hash, kind, grade_number, subject_code, scope,
                               seed, question_count, duration_s, late_write_tolerance_ms, feedback_mode,
                               negative_marks, invalid_item_treatment, scoring_policy_version, created_at)
    select form_id, user_id, 'load-' || :run || '-' || n || '-' || a, md5(form_id::text), 'practice', :grade,
           :subject, jsonb_build_object('mode', 'chapters', 'load_run', :run), (random() * 1e15)::bigint, :questions,
           null, 0, 'deferred', 0, 'EXCLUDE', :policy, started_at
    from load_forms
    """,
    """
    create temporary table load_items on commit drop as
    with pool as (select cast(:pool as jsonb) as qs)
    select f.form_id, f.attempt_id, f.started_at, p.position,
           (pool.qs -> ((f.seq * :questions + p.position) % jsonb_array_length(pool.qs))::int) as q
    from load_forms f cross join generate_series(1, cast(:questions as int)) p(position) cross join pool
    """,
    """
    insert into form_item (id, form_id, position, item_id, family_id, version_id, marks, option_order, grade_number,
                           subject_code)
    select gen_random_uuid(), form_id, position, (q->>'item_id')::uuid, (q->>'family_id')::uuid,
           (q->>'version_id')::uuid, 1, q->'options', :grade, :subject
    from load_items
    """,
    """
    create temporary table load_ops on commit drop as
    select i.attempt_id, i.position, r.revision, gen_random_uuid() as op_id,
           i.started_at + make_interval(secs => i.position * 40 + r.revision * 7) as admitted_at,
           case when r.revision = :revisions and random() < 0.6 then i.q->>'key'
                else (array['o1','o2','o3','o4'])[1 + floor(random() * 4)::int] end as option_id
    from load_items i cross join generate_series(1, cast(:revisions as int)) r(revision)
    """,
    """
    insert into attempt (id, form_id, user_id, status, started_at, deadline_at, tolerance_ms, cutoff_at, finalised_at,
                         finalise_reason, flagged, notebook_applied_at)
    select attempt_id, form_id, user_id, 'finalised', started_at, null, 0, null,
           started_at + make_interval(secs => :questions * 40 + :revisions * 7 + 60), 'manual', '[]'::jsonb, null
    from load_forms
    """,
    """
    insert into answer_op (id, attempt_id, op_id, payload_hash, position, revision, option_id, admitted_at,
                           disposition, via)
    select gen_random_uuid(), attempt_id, op_id, md5(op_id::text || coalesce(option_id, '')), position, revision,
           option_id, admitted_at, 'accepted', 'save'
    from load_ops
    """,
    """
    insert into attempt_answer (attempt_id, position, option_id, revision, op_id, saved_at)
    select attempt_id, position, option_id, revision, op_id, admitted_at
    from load_ops where revision = :revisions
    """,
    """
    insert into submission_receipt (id, attempt_id, idempotency_key, reason, admitted_at, answered_count,
                                    question_count, ledger_hash, included_ops)
    select gen_random_uuid(), f.attempt_id, 'load-' || f.attempt_id, 'manual',
           f.started_at + make_interval(secs => :questions * 40 + :revisions * 7 + 60), :questions, :questions,
           encode(sha256(convert_to(
               '[' || string_agg('[' || o.position || ', "' || coalesce(o.option_id, '') || '"]', ', '
                                 order by o.position) || ']', 'UTF8')), 'hex'),
           '[]'::jsonb
    from load_forms f join load_ops o on o.attempt_id = f.attempt_id and o.revision = :revisions
    group by f.attempt_id, f.started_at
    """,
    """
    insert into score_version (id, attempt_id, version, scoring_policy_version, adjudication_hash, status, raw,
                               maximum, percentage, items, reason, created_at)
    select gen_random_uuid(), i.attempt_id, 1, :policy, :empty_adjudications, 'scored',
           count(*) filter (where o.option_id = i.q->>'key'), :questions,
           round(100.0 * count(*) filter (where o.option_id = i.q->>'key') / :questions, 2),
           jsonb_agg(jsonb_build_object(
               'position', i.position, 'chosen', o.option_id, 'correct', o.option_id = i.q->>'key',
               'earned', case when o.option_id = i.q->>'key' then 1 else 0 end, 'max', 1, 'treatment', 'NONE')
               order by i.position),
           '', min(i.started_at) + make_interval(secs => :questions * 40 + :revisions * 7 + 60)
    from load_items i join load_ops o
      on o.attempt_id = i.attempt_id and o.position = i.position and o.revision = :revisions
    group by i.attempt_id
    """,
]


@dataclass
class Report:
    run: str
    database: str
    accounts: int
    attempts: int
    questions_per_attempt: int
    answer_revisions: int
    distinct_questions_available: int
    distinct_questions_used: int
    question_source: str
    seconds: float
    rows_per_second: float
    purchase_events: str = "none: no payment provider sandbox yet (B06)"
    academic_coverage: str = "none claimed: generated histories exercise storage and queries only"


def generate(engine: Engine, plan: Plan, *, allow_database: str | None = None) -> Report:
    from portal_api.config import get_settings
    from portal_api.modules.assessment.models import SCORING_POLICY_VERSION

    check_plan(plan)
    database = check_target(engine, allow_database)
    with engine.connect() as conn:
        pool = question_pool(conn, plan.grade, plan.subject)
    if len(pool) < plan.questions:
        raise Refused(
            f"Only {len(pool)} published Class {plan.grade} {plan.subject} questions exist; a test needs "
            f"{plan.questions}. Publish more questions or ask for fewer per test."
        )
    params: dict[str, Any] = {
        "issuer": get_settings().dev_auth_issuer,
        "run": plan.run,
        "attempts": plan.attempts,
        "questions": plan.questions,
        "revisions": plan.revisions,
        "grade": plan.grade,
        "subject": plan.subject,
        "policy": SCORING_POLICY_VERSION,
        "empty_adjudications": EMPTY_ADJUDICATIONS,
        "pool": json.dumps([{**q, "item_id": str(q["item_id"]), "family_id": str(q["family_id"]),
                              "version_id": str(q["version_id"])} for q in pool]),
    }  # fmt: skip
    started = time.monotonic()
    for first in range(1, plan.accounts + 1, BATCH_ACCOUNTS):
        last = min(first + BATCH_ACCOUNTS - 1, plan.accounts)
        with engine.begin() as conn:
            for sql in BATCH_SQL:
                conn.execute(text(sql), {**params, "first": first, "last": last})
    seconds = time.monotonic() - started
    with engine.connect() as conn:
        used = int(
            conn.execute(
                text(
                    "select count(distinct fi.family_id) from form_item fi join practice_form f on f.id = fi.form_id "
                    "where f.scope->>'load_run' = :run"
                ),
                {"run": plan.run},
            ).scalar_one()
        )
    rows = plan.accounts * (1 + plan.attempts * (4 + plan.questions * (2 + plan.revisions)))
    return Report(
        run=plan.run,
        database=database,
        accounts=plan.accounts,
        attempts=plan.accounts * plan.attempts,
        questions_per_attempt=plan.questions,
        answer_revisions=plan.answer_revisions,
        distinct_questions_available=len(pool),
        distinct_questions_used=used,
        question_source="published questions already in this database (development: labelled technical fixtures)",
        seconds=round(seconds, 2),
        rows_per_second=round(rows / seconds, 1) if seconds else 0.0,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--database-url", required=True)
    p.add_argument("--allow-database", help="Accept this database name even though it doesn't end in _load")
    p.add_argument("--accounts", type=int, default=1_000)
    p.add_argument("--attempts", type=int, default=3)
    p.add_argument("--questions", type=int, default=8)
    p.add_argument("--revisions", type=int, default=2)
    p.add_argument("--grade", type=int, default=11)
    p.add_argument("--subject", default="biology")
    p.add_argument("--run", default=uuid.uuid4().hex[:8])
    p.add_argument("--report", help="Write the JSON report here as well")
    a = p.parse_args(argv)
    plan = Plan(a.accounts, a.attempts, a.questions, a.revisions, a.grade, a.subject, a.run)
    try:
        report = generate(create_engine(a.database_url), plan, allow_database=a.allow_database)
    except Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    out = json.dumps(asdict(report), indent=2)
    print(out)
    if a.report:
        with open(a.report, "w", encoding="utf-8") as f:
            f.write(out + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
