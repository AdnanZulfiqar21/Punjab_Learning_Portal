"""Reviewed MCQ score corrections and score-version propagation (roadmap §5.7, P10.S3.T4, P08.S4.T1).

A confirmed defect is recorded as an adjudication of one exact question version, separate from its quarantine
availability and from every attempt snapshot:

* VOID (the question has no valid answer): each affected form applies its pinned `invalid_item_treatment`
  (EXCLUDE for practice, or CREDIT_ALL).
* KEY_ERROR (valid question, wrong published key): KEY_CORRECTION against the reviewed corrected option.

Only academic adjudicators in scope (MFA) record them, and only while the question is quarantined at the matching
level. A new correction for the same version supersedes the earlier one explicitly. Every finalised attempt whose
frozen form contains that version is re-scored from its immutable final-answer ledger with the complete effective set:
ScoreVersion n+1 only when that set changes (unique on attempt, policy and effective hash), so reruns and duplicate
jobs add nothing. Attempts still open when a correction lands get it at submission. The learner gets one
`score.revised` notice per new version; earlier versions stay in their history.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from portal_api.errors import Conflict, Unprocessable
from portal_api.modules.assessment import forms, scoring
from portal_api.modules.assessment.models import (
    SCORING_POLICY_VERSION,
    Attempt,
    FormItem,
    McqAdjudication,
    PracticeForm,
    ScoreVersion,
)
from portal_api.modules.audit.models import record
from portal_api.modules.content.models import ContentVersion
from portal_api.modules.identity.deps import Principal
from portal_api.modules.identity.permissions import Permission

log = logging.getLogger("portal.assessment.adjudications")

DEFECT_LEVEL = {"VOID": "VOID", "KEY_ERROR": "KEY_ERROR"}  # adjudication defect -> required quarantine level


def _now(db: Session) -> datetime:
    now: datetime = db.execute(select(func.clock_timestamp())).scalar_one()
    return now


def record_adjudication(
    db: Session,
    who: Principal,
    item_id: uuid.UUID,
    *,
    defect: str,
    reason: str,
    corrected_option_id: str | None = None,
) -> McqAdjudication:
    from portal_api.modules.content import workflow

    item = workflow.get_item(db, item_id, for_update=True)
    workflow._require_scoped(db, who, Permission.adjudicate, item)
    if item.kind != "mcq":
        raise Unprocessable("Score corrections apply to multiple-choice questions.")
    if defect not in DEFECT_LEVEL:
        raise Unprocessable("Choose VOID or KEY_ERROR.")
    if item.availability != "quarantined" or item.quarantine_level != DEFECT_LEVEL[defect]:
        raise Conflict(f"Quarantine the question at {DEFECT_LEVEL[defect]} before recording this correction.")
    if item.published_version_id is None:
        raise Conflict("This question has no published version to correct.")
    version = db.get(ContentVersion, item.published_version_id)
    assert version is not None
    options = [o["id"] for o in version.body.get("options", [])]
    if defect == "KEY_ERROR":
        if corrected_option_id not in options:
            raise Unprocessable("Choose the corrected answer from this question's options.")
        if corrected_option_id == version.body.get("correct_option_id"):
            raise Unprocessable("The corrected answer is the same as the published key.")
    elif corrected_option_id is not None:
        raise Unprocessable("A void question has no corrected answer.")
    prior = db.scalar(
        select(McqAdjudication)
        .where(McqAdjudication.version_id == version.id, McqAdjudication.status == "effective")
        .with_for_update()
    )
    if prior is not None and (prior.defect, prior.corrected_option_id) == (defect, corrected_option_id):
        raise Conflict("This correction is already in effect.")
    now = _now(db)
    if prior is not None:
        prior.status = "superseded"
        prior.superseded_at = now
        db.flush()  # one effective correction per version
    row = McqAdjudication(
        id=uuid.uuid4(),
        item_id=item.id,
        version_id=version.id,
        defect=defect,
        corrected_option_id=corrected_option_id,
        reason=reason.strip(),
        decided_by=who.user.id,
        decided_at=now,
        supersedes_id=prior.id if prior else None,
    )
    db.add(row)
    record(
        db,
        actor=who.user.id,
        action="assessment.score_correction_recorded",
        target_type="content_item",
        target_id=str(item.id),
        details={
            "adjudication": str(row.id),
            "version": version.number,
            "defect": defect,
            "corrected_option_id": corrected_option_id,
            "supersedes": str(prior.id) if prior else None,
            "reason": row.reason,
        },
    )
    db.commit()
    db.refresh(row)
    return row


def corrections(db: Session, item_id: uuid.UUID) -> list[McqAdjudication]:
    return list(
        db.scalars(
            select(McqAdjudication).where(McqAdjudication.item_id == item_id).order_by(McqAdjudication.decided_at)
        )
    )


def effective_for_form(db: Session, form: PracticeForm) -> list[scoring.Adjudication]:
    """The complete effective correction set for a frozen form, by position."""
    positions = {fi.version_id: fi.position for fi in form.items}
    if not positions:
        return []
    rows = db.scalars(
        select(McqAdjudication).where(
            McqAdjudication.version_id.in_(list(positions)), McqAdjudication.status == "effective"
        )
    )
    return [
        scoring.Adjudication(
            position=positions[r.version_id],
            treatment=form.invalid_item_treatment if r.defect == "VOID" else "KEY_CORRECTION",
            corrected_option_id=r.corrected_option_id,
        )
        for r in rows
    ]


def affected_attempts(db: Session, version_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        db.scalars(
            select(Attempt.id)
            .join(FormItem, FormItem.form_id == Attempt.form_id)
            .where(FormItem.version_id == version_id, Attempt.status == "finalised")
            .order_by(Attempt.finalised_at)
        )
    )


def affected_report(db: Session, item_id: uuid.UUID) -> list[dict[str, Any]]:
    """P08.S4.T2: per version of a question, the practice forms and attempts it reaches, grouped before start, active
    and released (finalised). Counts only; no learner identities."""
    from sqlalchemy import exists

    versions = db.scalars(
        select(ContentVersion).where(ContentVersion.item_id == item_id).order_by(ContentVersion.number)
    ).all()
    out = []
    for v in versions:
        form_ids = select(FormItem.form_id).where(FormItem.version_id == v.id)
        before = db.scalar(
            select(func.count())
            .select_from(PracticeForm)
            .where(PracticeForm.id.in_(form_ids), ~exists().where(Attempt.form_id == PracticeForm.id))
        )
        by_status = dict(
            db.execute(
                select(Attempt.status, func.count()).where(Attempt.form_id.in_(form_ids)).group_by(Attempt.status)
            ).all()
        )
        out.append(
            {
                "version": v.number,
                "status": v.status,
                "before_start": int(before or 0),
                "active": int(by_status.get("active", 0)),
                "released": int(by_status.get("finalised", 0)),
            }
        )
    return out


def _reason_text(adjs: list[scoring.Adjudication]) -> str:
    kinds = {a.treatment for a in adjs}
    parts = []
    if "EXCLUDE" in kinds:
        parts.append("a question found to have no valid answer was removed from your score")
    if "CREDIT_ALL" in kinds:
        parts.append("a question found to have no valid answer was credited to everyone")
    if "KEY_CORRECTION" in kinds:
        parts.append("a question's answer key was corrected after review")
    return ("After review, " + "; ".join(parts) + ".") if parts else "A correction was withdrawn after review."


def rescore(db: Session, attempt_id: uuid.UUID) -> ScoreVersion | None:
    """Re-score one finalised attempt with its complete effective correction set. Serialised per attempt; a new
    version only when that set changed. Commits its own short transaction."""
    from portal_api.modules.assessment import attempts
    from portal_api.modules.notifications import service as notifications

    attempt = db.scalar(select(Attempt).where(Attempt.id == attempt_id).with_for_update())
    if attempt is None or attempt.status != "finalised":
        db.rollback()
        return None
    form = db.get(PracticeForm, attempt.form_id)
    assert form is not None
    adjs = effective_for_form(db, form)
    digest = scoring.adjudication_hash(adjs)
    latest = attempts.latest_score(db, attempt.id)
    if latest is not None and (latest.scoring_policy_version, latest.adjudication_hash) == (
        SCORING_POLICY_VERSION,
        digest,
    ):
        db.rollback()
        return None
    seen = db.scalar(
        select(ScoreVersion.id).where(
            ScoreVersion.attempt_id == attempt.id,
            ScoreVersion.scoring_policy_version == SCORING_POLICY_VERSION,
            ScoreVersion.adjudication_hash == digest,
        )
    )
    if seen is not None:
        # An earlier version already used exactly this set (a correction was superseded back). Uniqueness keeps one
        # row per set; reinstating it needs an explicit new correction. Reported, never silently changed.
        log.warning("attempt %s: effective correction set matches an earlier score version; not re-scored", attempt.id)
        db.rollback()
        return None
    keys = forms.item_keys(db, form)
    result = scoring.score(
        [
            scoring.ItemKey(
                position=p, correct_option_id=k["correct_option_id"], option_ids=k["option_ids"], marks=k["marks"]
            )
            for p, k in keys.items()
        ],
        attempts._answers(db, attempt),
        negative_marks=form.negative_marks,
        adjudications=adjs,
    )
    reason = _reason_text(adjs)
    sv = ScoreVersion(
        attempt_id=attempt.id,
        version=(latest.version if latest else 0) + 1,
        scoring_policy_version=SCORING_POLICY_VERSION,
        adjudication_hash=digest,
        status=result.status,
        raw=result.raw,
        maximum=result.maximum,
        percentage=result.percentage,
        items=result.items,
        reason=reason,
    )
    db.add(sv)
    db.flush()
    from portal_api.modules.assessment import notebook

    notebook.apply_attempt(db, attempt, _now(db))  # a correction re-derives, never counts as a new response
    record(
        db,
        actor=None,
        action="attempt.rescored",
        target_type="attempt",
        target_id=str(attempt.id),
        details={"version": sv.version, "adjudication_hash": digest, "raw": sv.raw, "maximum": sv.maximum},
    )
    from portal_api.modules.assessment.sessions import held_forms

    if attempt.form_id not in held_forms(db, attempt.user_id):  # OCT9-01: a held result is released, not "revised"
        notifications.notify(
            db, attempt.user_id, "score.revised", {"reason": reason}, dedupe_key=f"mcq-score-{attempt.id}-{sv.version}"
        )
    db.commit()
    return sv


def propagate(db: Session, version_id: uuid.UUID) -> int:
    """Re-score every finalised attempt containing this question version. Idempotent; safe to rerun."""
    ids = affected_attempts(db, version_id)
    db.rollback()  # no transaction held between attempts
    return sum(1 for a in ids if rescore(db, a) is not None)


def summary(db: Session, adjudication: McqAdjudication) -> dict[str, Any]:
    return {"affected_attempts": len(affected_attempts(db, adjudication.version_id))}


def main() -> None:
    """`portal-mcq-regrade`: re-run propagation for every effective correction (recovery after an interruption)."""
    from portal_api.db import get_sessionmaker

    with get_sessionmaker()() as db:
        versions = list(db.scalars(select(McqAdjudication.version_id).where(McqAdjudication.status == "effective")))
        db.rollback()
        total = sum(propagate(db, v) for v in versions)
    print(f"re-scored {total} attempt(s) across {len(versions)} corrected question version(s)")
