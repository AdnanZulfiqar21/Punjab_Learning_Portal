"""Personal progress report (roadmap P12.S4.T2; PROGRESS-01).

Built from each finalised attempt's **latest** score version, so reviewed corrections are already reflected, and from
the mistake notebook. Every number has a written definition in `DEFINITIONS`. This is not a mastery claim: topic-level
evidence classification (P12.S2) is separate and not yet built, so nothing here says a learner has demonstrated an
outcome.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from portal_api.modules.assessment.models import Attempt, FormItem, PracticeForm, ScoreVersion

REPORT_VERSION = 1
DEFINITIONS = {
    "tests": "Submitted practice, mock and review tests containing questions from this class and subject. A test "
    "mixing classes or subjects counts once in each it contains; its overall result is shown once under recent tests.",
    "questions_answered": "Questions you chose an answer for, excluding questions withdrawn after review.",
    "correct": "Answered questions marked correct under the latest score version (corrected keys apply).",
    "accuracy": "Correct ÷ answered, as a percentage. Credited-to-everyone questions are not counted as answered.",
    "score": "Marks earned ÷ marks available in that test's latest score version, after any reviewed corrections.",
    "notebook": "Questions you answered wrongly that are open, mastered after spaced review, or withdrawn.",
    "results_pending": "Submitted scheduled mocks whose results aren't released yet; they count once released.",
}


def report(db: Session, user_id: uuid.UUID) -> dict[str, Any]:
    from portal_api.modules.assessment import notebook
    from portal_api.modules.assessment.notebook import MistakeEntry
    from portal_api.modules.assessment.sessions import held_forms

    notebook.sync(db, user_id)
    held = held_forms(db, user_id)  # OCT9-01: a held scheduled mock adds nothing until its results are released

    latest = (  # this learner's attempts only
        select(ScoreVersion.attempt_id, func.max(ScoreVersion.version).label("v"))
        .join(Attempt, Attempt.id == ScoreVersion.attempt_id)
        .where(Attempt.user_id == user_id)
        .group_by(ScoreVersion.attempt_id)
        .subquery()
    )
    rows = db.execute(
        select(Attempt, PracticeForm, ScoreVersion)
        .join(PracticeForm, PracticeForm.id == Attempt.form_id)
        .join(latest, latest.c.attempt_id == Attempt.id)
        .join(ScoreVersion, (ScoreVersion.attempt_id == Attempt.id) & (ScoreVersion.version == latest.c.v))
        .where(Attempt.user_id == user_id, Attempt.status == "finalised")
        .order_by(Attempt.finalised_at.desc())
    ).all()
    pending = sum(1 for _, form, _ in rows if form.id in held)
    rows = [r for r in rows if r[1].id not in held]
    subjects: dict[tuple[int, str], dict[str, Any]] = {}
    recent: list[dict[str, Any]] = []
    form_ids = list({form.id for _, form, _ in rows})
    bucket_of: dict[tuple[uuid.UUID, int], tuple[int, str]] = {
        (f, p): (g, s)
        for f, p, g, s in db.execute(
            select(FormItem.form_id, FormItem.position, FormItem.grade_number, FormItem.subject_code).where(
                FormItem.form_id.in_(form_ids)
            )
        ).all()
    } if form_ids else {}  # fmt: skip
    for attempt, form, score in rows:
        parts = {
            bucket_of[(form.id, int(r["position"]))] for r in score.items if (form.id, int(r["position"])) in bucket_of
        }
        for key in parts:
            agg = subjects.setdefault(
                key,
                {
                    "grade": key[0],
                    "subject": key[1],
                    "tests": 0,
                    "questions_answered": 0,
                    "correct": 0,
                    "last_activity": None,
                },
            )
            agg["tests"] += 1
            if agg["last_activity"] is None or (attempt.finalised_at and attempt.finalised_at > agg["last_activity"]):
                agg["last_activity"] = attempt.finalised_at
        for item in score.items:
            if item.get("treatment") in ("EXCLUDE", "CREDIT_ALL") or item.get("chosen") is None:
                continue
            bucket = bucket_of.get((form.id, int(item["position"])))
            if bucket is None:
                continue
            subjects[bucket]["questions_answered"] += 1
            subjects[bucket]["correct"] += 1 if item.get("correct") else 0
        if len(recent) < 30:
            recent.append(
                {
                    "attempt_id": str(attempt.id),
                    "kind": form.kind,
                    "mode": (form.scope or {}).get("mode", "chapters"),
                    "grade": form.grade_number,
                    "subject": form.subject_code,
                    "finished_at": attempt.finalised_at,
                    "raw": score.raw,
                    "maximum": score.maximum,
                    "percentage": float(score.percentage) if score.percentage is not None else None,
                    "score_version": score.version,
                    "status": score.status,
                    "parts": [{"grade": g, "subject": s} for g, s in sorted(parts)],
                }
            )
    for agg in subjects.values():
        n = agg["questions_answered"]
        agg["accuracy"] = round(100 * agg["correct"] / n, 1) if n else None
    book = dict(
        db.execute(
            select(MistakeEntry.status, func.count())
            .where(MistakeEntry.user_id == user_id)
            .group_by(MistakeEntry.status)
        ).all()
    )
    now: datetime = db.execute(select(func.now())).scalar_one()
    return {
        "report_version": REPORT_VERSION,
        "generated_at": now,
        "definitions": DEFINITIONS,
        "subjects": sorted(subjects.values(), key=lambda a: (a["grade"], a["subject"])),
        "recent": recent,
        "notebook": {s: int(book.get(s, 0)) for s in ("open", "mastered", "voided")},
        "results_pending": pending,
    }
