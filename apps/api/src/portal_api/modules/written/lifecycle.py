"""Written script lifecycle timings for operators (roadmap W09.S1.T1; LIFECYCLE-01).

From timestamps already stored, for scripts started in a recent window (optionally one class and subject):

* **upload:** each page's time from the start (pages uploaded while writing) or from the end of writing (pages
  uploaded afterwards), counted per page;
* **seal:** from the start to the submission receipt;
* **queue:** from a first-marking case opening to the start of the marking that released it;
* **review:** from that marking start to the release (elapsed time, breaks included: MARKING-TIME-01);
* **publication:** from the receipt to the first released result.

Every stage reports its own count, so a latency is never read without the number of scripts behind it, and the
script outcomes are counted separately: accepted (sealed), not submitted (expired, with the plan-withdrawn share),
pending, delayed, released by a teacher and released automatically. Automatic reading and assessment publish nothing
in R0 (B10), so those stages are listed as not running rather than as zero time.

Medians and 90th percentiles over small samples are shown with their counts, not hidden: what sample size is enough
is an operating decision. These are measures of this deployment's own traffic, not capacity evidence (P20).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, and_, exists, extract, func, select, true
from sqlalchemy.orm import Session

from portal_api.modules.written.models import WrittenAttempt, WrittenForm, WrittenPage, WrittenReceipt
from portal_api.modules.written.review import WrittenReviewCase, WrittenScoreVersion

WINDOW_DAYS = 30


def _minutes(start: Any, end: Any) -> ColumnElement[Any]:
    return extract("epoch", end - start) / 60.0


def report(
    db: Session, *, days: int = WINDOW_DAYS, grade: int | None = None, subject: str | None = None
) -> dict[str, Any]:
    now: datetime = db.execute(select(func.now())).scalar_one()
    since = now - timedelta(days=days)
    scope: list[ColumnElement[bool]] = [WrittenAttempt.started_at >= since]
    if grade is not None:
        scope.append(WrittenForm.grade_number == grade)
    if subject is not None:
        scope.append(WrittenForm.subject_code == subject)
    attempts = select(WrittenAttempt).join(WrittenForm, WrittenForm.id == WrittenAttempt.form_id).where(*scope)
    a = attempts.subquery()

    def stage(name: str, description: str, value: ColumnElement[Any], query: Any) -> dict[str, Any]:
        sub = query.add_columns(value.label("m")).subquery()
        n, median, p90 = db.execute(
            select(
                func.count(sub.c.m),
                func.percentile_cont(0.5).within_group(sub.c.m),
                func.percentile_cont(0.9).within_group(sub.c.m),
            )
        ).one()
        return {
            "stage": name,
            "description": description,
            "count": int(n),
            "median_minutes": round(float(median), 1) if median is not None else None,
            "p90_minutes": round(float(p90), 1) if p90 is not None else None,
        }

    pages = select().select_from(WrittenPage).join(a, a.c.id == WrittenPage.attempt_id)
    pages = pages.where(WrittenPage.status == "uploaded")
    receipts = select().select_from(WrittenReceipt).join(a, a.c.id == WrittenReceipt.attempt_id)
    initial = (
        select()
        .select_from(WrittenReviewCase)
        .join(a, a.c.id == WrittenReviewCase.attempt_id)
        .where(WrittenReviewCase.case_kind == "initial")
    )
    first_release = (
        select(WrittenReviewCase.attempt_id, func.min(WrittenReviewCase.released_at).label("released_at"))
        .where(WrittenReviewCase.case_kind == "initial", WrittenReviewCase.released_at.is_not(None))
        .group_by(WrittenReviewCase.attempt_id)
        .subquery()
    )
    stages = [
        stage(
            "upload_while_writing",
            "Minutes from the start to each page uploaded before writing ended (per page)",
            _minutes(a.c.started_at, WrittenPage.uploaded_at),
            pages.where(a.c.writing_deadline_at.is_not(None), WrittenPage.uploaded_at <= a.c.writing_deadline_at),
        ),
        stage(
            "upload_after_writing",
            "Minutes from the end of writing to each page uploaded afterwards, or from the start when untimed",
            _minutes(func.coalesce(a.c.writing_deadline_at, a.c.started_at), WrittenPage.uploaded_at),
            pages.where((a.c.writing_deadline_at.is_(None)) | (WrittenPage.uploaded_at > a.c.writing_deadline_at)),
        ),
        stage(
            "seal",
            "Minutes from the start to the submission receipt (accepted scripts)",
            _minutes(a.c.started_at, WrittenReceipt.admitted_at),
            receipts,
        ),
        stage(
            "queue",
            "Minutes from a first-marking case opening to the start of the marking that released it",
            _minutes(WrittenReviewCase.opened_at, WrittenReviewCase.marking_started_at),
            initial.where(
                WrittenReviewCase.released_at.is_not(None), WrittenReviewCase.marking_started_at.is_not(None)
            ),
        ),
        stage(
            "review",
            "Minutes from that marking start to the release: elapsed time with breaks included, not working time",
            _minutes(WrittenReviewCase.marking_started_at, WrittenReviewCase.released_at),
            initial.where(
                WrittenReviewCase.released_at.is_not(None), WrittenReviewCase.marking_started_at.is_not(None)
            ),
        ),
        stage(
            "publication",
            "Minutes from the submission receipt to the first released result",
            _minutes(WrittenReceipt.admitted_at, first_release.c.released_at),
            receipts.join(first_release, first_release.c.attempt_id == WrittenReceipt.attempt_id),
        ),
    ]

    def count(*where: ColumnElement[bool]) -> int:
        return int(db.scalar(select(func.count()).select_from(a).where(*where)) or 0)

    released = exists().where(WrittenScoreVersion.attempt_id == a.c.id, WrittenScoreVersion.released.is_(True))

    def by_method(method: str) -> ColumnElement[bool]:
        return exists().where(
            WrittenScoreVersion.attempt_id == a.c.id,
            WrittenScoreVersion.released.is_(True),
            WrittenScoreVersion.decision_method == method,
        )

    overdue = exists().where(
        WrittenReviewCase.attempt_id == a.c.id,
        WrittenReviewCase.status == "queued",
        WrittenReviewCase.due_at < now,
    )
    sealed = a.c.status == "sealed"
    outcomes = {
        "started": count(true()),
        "accepted": count(sealed),
        "not_submitted": count(a.c.status == "expired"),
        "not_submitted_plan_withdrawn": count(and_(a.c.status == "expired", a.c.end_reason == "plan_withdrawn")),
        "still_writing": count(a.c.status == "active"),
        "pending": count(sealed, ~released),
        "delayed": count(sealed, overdue),
        "released_by_teacher": count(by_method("TEACHER")),
        "released_automatically": count(by_method("AI")),
    }
    return {
        "since": since,
        "days": days,
        "grade": grade,
        "subject": subject,
        "outcomes": outcomes,
        "stages": stages,
        "not_running": [
            "reading: automatic reading of scripts is not in use (B10)",
            "assessment: automatic assessment publishes nothing in R0 (B10)",
        ],
    }
