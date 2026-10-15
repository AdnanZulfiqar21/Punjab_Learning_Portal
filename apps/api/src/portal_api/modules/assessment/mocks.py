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
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from portal_api.errors import Conflict, NotFound, Unprocessable
from portal_api.modules.assessment import forms
from portal_api.modules.assessment.models import FormItem, PracticeForm
from portal_api.modules.assessment.profiles import ExamProfile, ExamProfileVersion, catalogue_problems
from portal_api.modules.content.models import ContentItem, ContentVersion
from portal_api.modules.identity.deps import Principal

Pool = dict[uuid.UUID, list[tuple[ContentItem, ContentVersion]]]


class SectionShortage(Exception):
    def __init__(self, section: int, band: str | None = None, needed: int = 0, available: int = 0) -> None:
        super().__init__(f"section {section} ran out of distinct questions" + (f" at {band}" if band else ""))
        self.section, self.band, self.needed, self.available = section, band, needed, available


BANDS = ("easy", "medium", "hard")


def allocate(n: int, mix: Mapping[str, int]) -> dict[str, int]:
    """P09.S3.T1 (ALLOCATION-01): `n` questions over a difficulty mix in percent, by largest-remainder rounding. Each
    band gets its whole share; the questions left go to the largest remainders, ties to the earlier band (easy,
    medium, hard). Always adds up to `n`, and the same inputs always give the same counts."""
    shares = {b: n * int(mix.get(b, 0)) for b in BANDS}  # hundredths of a question
    counts = {b: shares[b] // 100 for b in BANDS}
    left = n - sum(counts.values())
    for b in sorted(BANDS, key=lambda b: (-(shares[b] % 100), BANDS.index(b)))[:left]:
        counts[b] += 1
    return counts


def difficulty(version: Any) -> str | None:
    """The editorial difficulty a reviewed version carries (MCQ metadata), if any."""
    value = ((version.body or {}).get("metadata") or {}).get("difficulty")
    return value if value in BANDS else None


def _draw(
    rng: random.Random, pool: Mapping[uuid.UUID, forms.Members], n: int, seen: set[uuid.UUID]
) -> tuple[list[uuid.UUID], int]:
    unseen = sorted((f for f in pool if f not in seen), key=str)
    picked = rng.sample(unseen, min(n, len(unseen)))
    reused = n - len(picked)
    if reused:  # not enough new questions: reuse some already seen, and say so on the form
        picked += rng.sample(sorted((f for f in pool if f in seen), key=str), reused)
    return picked, reused


def select_sections(
    sections: Sequence[tuple[int, Mapping[uuid.UUID, forms.Members]]],
    seen: set[uuid.UUID],
    seed: int,
    mixes: Sequence[Mapping[str, int] | None] | None = None,
) -> list[tuple[list[forms.Pick], int]]:
    """Each section's questions, in profile order, with how many were reused from earlier mocks.

    Unseen families come first; a family is never used twice in one mock, even when two sections' pools share it
    (GENERATOR-PROPERTIES-01). Reproducible from the stored seed, independent of pool order. A section with a
    difficulty mix (ALLOCATION-01) draws each band's allocated count from families with a variant reviewed at that
    difficulty, takes that variant, and is shuffled so the order doesn't give the difficulty away; a band that runs
    short refuses the whole test rather than borrowing from another band."""
    rng = random.Random(seed)  # noqa: S311 - reproducible sampling from a stored seed, not a secret
    taken: set[uuid.UUID] = set()
    out = []
    for number, (n, pool) in enumerate(sections, start=1):
        free = {f: pool[f] for f in pool if f not in taken}
        mix = mixes[number - 1] if mixes else None
        if not mix:
            if len(free) < n:
                raise SectionShortage(number)
            picked, reused = _draw(rng, free, n, seen)
            taken.update(picked)
            out.append(([(f, *forms.variant(rng, free[f])) for f in picked], reused))
            continue
        picks: list[forms.Pick] = []
        reused_all = 0
        for band, k in allocate(n, mix).items():
            if k == 0:
                continue
            banded = {f: [m for m in ms if difficulty(m[1]) == band] for f, ms in free.items() if f not in taken}
            banded = {f: ms for f, ms in banded.items() if ms}
            if len(banded) < k:
                raise SectionShortage(number, band, k, len(banded))
            picked, reused = _draw(rng, banded, k, seen)
            taken.update(picked)
            reused_all += reused
            picks += [(f, *forms.variant(rng, banded[f])) for f in picked]
        rng.shuffle(picks)
        out.append((picks, reused_all))
    return out


def _section_pool(db: Session, subject: str, grades: list[int], question_pool: str) -> Pool:
    pool: Pool = {}
    for g in grades:
        chapters = [c.id for c in forms._book_chapters(db, g, subject)]
        if chapters:
            pool.update(forms._pool(db, g, subject, chapters, [], question_pool))
    return pool


def _seen_families(db: Session, user_id: uuid.UUID) -> set[uuid.UUID]:
    """Question families this learner has already met in earlier mocks (exposure, P08.S3.T3)."""
    return set(
        db.scalars(
            select(FormItem.family_id)
            .join(PracticeForm, PracticeForm.id == FormItem.form_id)
            .where(PracticeForm.owner_id == user_id, PracticeForm.kind == "mock")
        )
    )


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
        pool = _section_pool(db, s["subject"], s["grades"], version.rules.get("question_pool", "mock"))
        available = len(pool)
        enough = available >= int(s["questions"])
        bands: list[dict[str, Any]] | None = None
        if s.get("difficulty_mix"):  # ALLOCATION-01: each band needs its own count
            bands = []
            for b, k in allocate(int(s["questions"]), s["difficulty_mix"]).items():
                if k:
                    have = sum(1 for ms in pool.values() if any(difficulty(v) == b for _, v in ms))
                    bands.append({"difficulty": b, "required": k, "available": have})
                    enough = enough and have >= k
        sections.append({**s, "available": available, "enough": enough, "bands": bands})
    problems = catalogue_problems(db, version.rules["sections"])
    return {
        "code": profile.code,
        "version": version.version,
        "sections": sections,
        "problems": problems,
        "ready": all(x["enough"] for x in sections)
        and not problems
        and version.rules.get("solution_release") == "after_submission",
        "scheduled": version.rules.get("solution_release") != "after_submission",
    }


def build(db: Session, who: Principal, code: str, idempotency_key: str) -> PracticeForm:
    profile, version = _published(db, code)
    return build_from(db, who, profile, version, idempotency_key=idempotency_key)


def build_from(
    db: Session,
    who: Principal,
    profile: ExamProfile,
    version: ExamProfileVersion,
    *,
    idempotency_key: str,
    duration_s: int | None = None,
    extra_scope: dict[str, Any] | None = None,
    allow_scheduled: bool = False,
    copy_from: PracticeForm | None = None,
) -> PracticeForm:
    """Build the frozen mock form. Scheduled sessions (SCHEDULE-01) pass their own time limit and window details.

    P09.S3.T3 (FIXED-FORMS-01): a practice mock is a *varied* form, sampled for this learner (unseen questions
    first). A scheduled session is a *fixed comparable* form: its first form is sampled without regard to anyone's
    history, and `copy_from` gives every later participant exactly that form (question versions, order, option
    permutations, passages, marks). Equivalence beyond "the same questions" is not claimed."""
    from portal_api.modules.access import service as access

    req = {"mock": profile.code, "version_id": str(version.id), "scope": extra_scope or {}}
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
    access.require_access(db, who.user.id, purpose="Mock tests", need=access.Need(exam=profile.code))
    if copy_from is not None:  # the session's fixed form, as frozen: today's pool doesn't change it
        return _copy(db, who, copy_from, idempotency_key=idempotency_key, request_hash=rhash)
    rules = version.rules
    if rules.get("solution_release") != "after_submission" and not allow_scheduled:
        raise Conflict("Scheduled mocks with delayed solutions aren't available yet.", code_reason="MOCK_SCHEDULED")
    problems = catalogue_problems(db, rules["sections"])  # P05.S4.T3: never mix book editions silently
    if problems:
        raise Conflict(
            "This test pattern doesn't match the current books, so it can't be used until it is corrected.",
            code_reason="PATTERN_UNSUPPORTED",
            problems=problems,
        )
    question_pool = rules.get("question_pool", "mock")
    pools = [(s, _section_pool(db, s["subject"], s["grades"], question_pool)) for s in rules["sections"]]
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
    comparable = allow_scheduled  # session forms are fixed and shared; practice mocks are varied per learner
    seed = secrets.randbits(62)
    seen = set() if comparable else _seen_families(db, who.user.id)
    try:
        chosen = select_sections(
            [(int(s["questions"]), p) for s, p in pools], seen, seed, [s.get("difficulty_mix") for s, _ in pools]
        )
    except SectionShortage as e:  # sections that share questions, or a difficulty band that runs short
        s = rules["sections"][e.section - 1]
        short_row: dict[str, Any] = {"subject": s["subject"], "grades": s["grades"], "required": int(s["questions"])}
        if e.band:
            short_row |= {"difficulty": e.band, "required": e.needed, "available": e.available}
        raise Unprocessable(
            "There aren't enough approved questions for this test pattern yet. A smaller practice test is available "
            "instead; it won't be a full mock.",
            code_reason="POOL_SHORTAGE",
            sections=[short_row],
        ) from None
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
            "question_pool": question_pool,
            "sections": [],
            "form_type": "fixed" if comparable else "varied",
            **(extra_scope or {}),
        },
        seed=seed,
        question_count=total,
        duration_s=duration_s if duration_s is not None else int(rules["duration_minutes"]) * 60,
        late_write_tolerance_ms=int(rules.get("late_write_tolerance_ms", 0)),
        feedback_mode="deferred",
        negative_marks=int(rules.get("negative_marks", 0)),
        invalid_item_treatment=rules.get("invalid_item_treatment", "EXCLUDE"),
    )
    db.add(form)
    position = 0
    sections = []
    for (s, _), (picks, reused) in zip(pools, chosen, strict=True):
        start = position + 1
        for family, item, cv, option_ids in forms.group_by_passage(picks):  # within the section (PASSAGES-01)
            position += 1
            db.add(
                FormItem(
                    form_id=form.id,
                    position=position,
                    item_id=item.id,
                    family_id=family,
                    version_id=cv.id,
                    marks=int(rules.get("marks_per_question", 1)),
                    option_order=option_ids,
                    grade_number=item.grade_number,
                    subject_code=item.subject_code,
                    passage_version_id=forms.passage_version(db, cv),
                )
            )
        row = {"subject": s["subject"], "grades": s["grades"], "from": start, "to": position, "reused": reused}
        if s.get("difficulty_mix"):  # ALLOCATION-01: the counts this form was built with, for the audit trail
            row["difficulty"] = allocate(int(s["questions"]), s["difficulty_mix"])
        sections.append(row)
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


def _copy(
    db: Session, who: Principal, master: PracticeForm, *, idempotency_key: str, request_hash: str
) -> PracticeForm:
    """FIXED-FORMS-01: this learner's copy of a session's fixed form (the master's items, exactly)."""
    form = PracticeForm(
        id=uuid.uuid4(),
        owner_id=who.user.id,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        kind=master.kind,
        grade_number=master.grade_number,
        subject_code=master.subject_code,
        scope={**master.scope, "fixed_from": str(master.id)},
        seed=master.seed,
        question_count=master.question_count,
        duration_s=master.duration_s,
        late_write_tolerance_ms=master.late_write_tolerance_ms,
        feedback_mode=master.feedback_mode,
        negative_marks=master.negative_marks,
        invalid_item_treatment=master.invalid_item_treatment,
    )
    db.add(form)
    for fi in sorted(master.items, key=lambda i: i.position):
        db.add(
            FormItem(
                form_id=form.id,
                position=fi.position,
                item_id=fi.item_id,
                family_id=fi.family_id,
                version_id=fi.version_id,
                marks=fi.marks,
                option_order=list(fi.option_order),
                grade_number=fi.grade_number,
                subject_code=fi.subject_code,
                passage_version_id=fi.passage_version_id,
            )
        )
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
