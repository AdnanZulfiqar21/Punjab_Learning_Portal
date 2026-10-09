"""Official-pattern mock tests built from a published exam profile (roadmap P09.S2.T1/T2, P09.S3.T1-T3; MOCK-01).

A mock is a frozen practice form of `kind="mock"`. Each section of the published profile version draws its question
count from approved, live, unique question families of that subject in that section's classes. Sections are ordered as
in the profile, and duplicates and sibling variants are impossible (one question per family). Before the first answer
the form freezes:

* the profile version (pinned in `scope`);
* question versions, order and option permutations;
* duration, late-write tolerance, marks, negative marking and the invalid-item correction policy, all from the
  profile.

Later profile versions never change it. A shortage in any section blocks the mock, with every section's available
and required count reported (P09.S3.T2). The learner is offered a clearly labelled smaller practice test instead,
never a quietly shrunk mock. Scheduled windows and delayed solution release (P09.S2.T3) aren't built, so profiles
that need them can't be started yet.

*Provisional:* mocks draw from the same approved pool as practice; protected mock pools with exposure policies
(P08.S3.T3) are not built.
"""

from __future__ import annotations

import hashlib
import json
import random
import secrets
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from portal_api.errors import Conflict, NotFound, Unprocessable
from portal_api.modules.assessment import forms
from portal_api.modules.assessment.models import FormItem, PracticeForm
from portal_api.modules.assessment.profiles import ExamProfile, ExamProfileVersion
from portal_api.modules.content.models import ContentItem, ContentVersion
from portal_api.modules.identity.deps import Principal

Pool = dict[uuid.UUID, list[tuple[ContentItem, ContentVersion]]]


def _section_pool(db: Session, subject: str, grades: list[int]) -> Pool:
    pool: Pool = {}
    for g in grades:
        chapters = [c.id for c in forms._book_chapters(db, g, subject)]
        if chapters:
            pool.update(forms._pool(db, g, subject, chapters, []))
    return pool


def _published(db: Session, code: str) -> tuple[ExamProfile, ExamProfileVersion]:
    row = db.execute(
        select(ExamProfile, ExamProfileVersion)
        .join(ExamProfileVersion, ExamProfileVersion.profile_id == ExamProfile.id)
        .where(ExamProfile.code == code.strip().upper(), ExamProfileVersion.status == "published")
    ).first()
    if row is None:
        raise NotFound("No published test pattern with that code.")
    return row[0], row[1]


def readiness(db: Session, code: str) -> dict[str, Any]:
    """Per-section availability for the current published version (counts only)."""
    profile, version = _published(db, code)
    sections = []
    for s in version.rules["sections"]:
        available = len(_section_pool(db, s["subject"], s["grades"]))
        sections.append({**s, "available": available, "enough": available >= int(s["questions"])})
    return {
        "code": profile.code,
        "version": version.version,
        "sections": sections,
        "ready": all(x["enough"] for x in sections) and version.rules.get("solution_release") == "after_submission",
        "scheduled": version.rules.get("solution_release") != "after_submission",
    }


def build(db: Session, who: Principal, code: str, idempotency_key: str) -> PracticeForm:
    from portal_api.modules.access import service as access

    profile, version = _published(db, code)
    req = {"mock": profile.code, "version_id": str(version.id)}
    rhash = hashlib.sha256(json.dumps(req, sort_keys=True).encode()).hexdigest()
    existing = db.scalar(
        select(PracticeForm).where(
            PracticeForm.owner_id == who.user.id, PracticeForm.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        if existing.request_hash != rhash:
            raise Conflict("This request key was already used for a different test.")
        return existing
    access.require_access(db, who.user.id, purpose="Mock tests")
    rules = version.rules
    if rules.get("solution_release") != "after_submission":
        raise Conflict("Scheduled mocks with delayed solutions aren't available yet.", code_reason="MOCK_SCHEDULED")
    pools = [(s, _section_pool(db, s["subject"], s["grades"])) for s in rules["sections"]]
    short = [
        {"subject": s["subject"], "grades": s["grades"], "required": int(s["questions"]), "available": len(p)}
        for s, p in pools
        if len(p) < int(s["questions"])
    ]
    if short:
        raise Unprocessable(
            "There aren't enough approved questions for this test pattern yet. A smaller practice test is available "
            "instead; it won't be a full mock.",
            code_reason="POOL_SHORTAGE",
            sections=short,
        )
    seed = secrets.randbits(62)
    rng = random.Random(seed)  # noqa: S311 - reproducible sampling from a stored seed, not a secret
    total = sum(int(s["questions"]) for s, _ in pools)
    first = rules["sections"][0]
    form = PracticeForm(
        id=uuid.uuid4(),
        owner_id=who.user.id,
        idempotency_key=idempotency_key,
        request_hash=rhash,
        kind="mock",
        grade_number=max(first["grades"]),
        subject_code=first["subject"],
        scope={
            "mode": "mock",
            "profile": profile.code,
            "profile_version_id": str(version.id),
            "profile_version": version.version,
            "year": version.year,
            "sections": [],
        },
        seed=seed,
        question_count=total,
        duration_s=int(rules["duration_minutes"]) * 60,
        late_write_tolerance_ms=int(rules.get("late_write_tolerance_ms", 0)),
        feedback_mode="deferred",
        negative_marks=int(rules.get("negative_marks", 0)),
        invalid_item_treatment=rules.get("invalid_item_treatment", "EXCLUDE"),
    )
    db.add(form)
    position = 0
    sections = []
    for s, pool in pools:
        start = position + 1
        for family in rng.sample(sorted(pool, key=str), int(s["questions"])):
            position += 1
            item, cv = rng.choice(sorted(pool[family], key=lambda iv: str(iv[0].id)))
            option_ids = [o["id"] for o in cv.body["options"]]
            if cv.body.get("shuffle_options", True):
                rng.shuffle(option_ids)
            db.add(
                FormItem(
                    form_id=form.id,
                    position=position,
                    item_id=item.id,
                    family_id=family,
                    version_id=cv.id,
                    marks=int(rules.get("marks_per_question", 1)),
                    option_order=option_ids,
                )
            )
        sections.append({"subject": s["subject"], "grades": s["grades"], "from": start, "to": position})
    form.scope = {**form.scope, "sections": sections}
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(PracticeForm).where(
                PracticeForm.owner_id == who.user.id, PracticeForm.idempotency_key == idempotency_key
            )
        )
        if existing is None:
            raise
        return existing
    db.refresh(form)
    return form
