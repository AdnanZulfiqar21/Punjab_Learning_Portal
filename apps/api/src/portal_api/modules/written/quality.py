"""Reviewer quality: overrides, upheld rechecks and conflicts per marker (W06.S3.T3, part; REVIEWER-QUALITY-01).

For academic adjudicators, per marker in their academic scope over a recent window:

* decisions the marker released;
* of those, how many a learner asked to recheck, and whether another teacher **changed** the marks or **upheld** them
  (a recheck version compared with the version it reviewed, question by question);
* how often an approved marking-guide correction sent the marker's work back to a teacher (a conflicting regrade);
* academic reviews the marker raised for methods the guide doesn't cover (ACADEMIC-REVIEW-01).

Raw counts only. No threshold says a marker is good or bad: what counts as a concerning rate is the academic lead's
decision (B01), and a few rechecks say little. Systematic guide problems go to academic review and rubric correction.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from portal_api.modules.identity.deps import Principal
from portal_api.modules.identity.models import AppUser
from portal_api.modules.written import adjudication
from portal_api.modules.written.academic import AcademicReview
from portal_api.modules.written.review import WrittenReviewCase, WrittenScoreVersion

WINDOW_DAYS = 90


def report(db: Session, who: Principal, days: int = WINDOW_DAYS) -> list[dict[str, Any]]:
    since = func.now() - timedelta(days=days)
    scope = adjudication.scope_clause(db, who, WrittenReviewCase.grade_number, WrittenReviewCase.subject_code)
    rows: dict[uuid.UUID, dict[str, Any]] = defaultdict(
        lambda: {
            "decisions": 0,
            "rechecked": 0,
            "changed_on_recheck": 0,
            "upheld_on_recheck": 0,
            "teacher_regrades": 0,
            "academic_reviews_raised": 0,
            "scopes": set(),
        }
    )

    decided = db.execute(
        select(WrittenScoreVersion.assessor_id, WrittenReviewCase.grade_number, WrittenReviewCase.subject_code)
        .join(WrittenReviewCase, WrittenReviewCase.id == WrittenScoreVersion.case_id)
        .where(
            scope,
            WrittenScoreVersion.released.is_(True),
            WrittenScoreVersion.decision_method == "TEACHER",
            WrittenScoreVersion.assessor_id.is_not(None),
            WrittenScoreVersion.created_at > since,
        )
    ).all()
    for marker, grade, subject in decided:
        if marker is None:
            continue
        rows[marker]["decisions"] += 1
        rows[marker]["scopes"].add((grade, subject))

    later, earlier = aliased(WrittenScoreVersion), aliased(WrittenScoreVersion)
    followed = db.execute(
        select(
            later.case_kind, later.decision_method, later.question_units, earlier.question_units, earlier.assessor_id
        )
        .join(earlier, earlier.id == later.prior_version_id)
        .join(WrittenReviewCase, WrittenReviewCase.id == later.case_id)
        .where(
            scope,
            later.released.is_(True),
            later.created_at > since,
            later.case_kind.in_(("recheck", "regrade")),
            earlier.decision_method == "TEACHER",
            earlier.assessor_id.is_not(None),
        )
    ).all()
    for kind, method, after, before, marker in followed:
        if marker is None:
            continue
        if kind == "recheck":
            rows[marker]["rechecked"] += 1
            rows[marker]["changed_on_recheck" if (after or {}) != (before or {}) else "upheld_on_recheck"] += 1
        elif method == "TEACHER":
            rows[marker]["teacher_regrades"] += 1  # a correction conflicted with this marker's decision

    raised = db.execute(
        select(AcademicReview.raised_by, func.count())
        .where(
            adjudication.scope_clause(db, who, AcademicReview.grade_number, AcademicReview.subject_code),
            AcademicReview.raised_at > since,
        )
        .group_by(AcademicReview.raised_by)
    ).all()
    for marker, n in raised:
        rows[marker]["academic_reviews_raised"] += int(n)

    emails = {u.id: u.email for u in db.scalars(select(AppUser).where(AppUser.id.in_(list(rows))))} if rows else {}
    out = []
    for marker, r in rows.items():
        out.append(
            {
                "reviewer_id": marker,
                "reviewer": emails.get(marker) or str(marker)[:8],
                **{k: v for k, v in r.items() if k != "scopes"},
                "scopes": sorted(f"{g}:{s}" for g, s in r["scopes"]),
            }
        )
    return sorted(out, key=lambda r: (-r["decisions"], r["reviewer"]))
