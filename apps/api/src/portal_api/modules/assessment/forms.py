"""Practice form generation (P09.S1.T1, P09.S3) and keyless learner snapshots (P08.S2.T3).

The pool is every *published, live* question in the requested chapters/topics, grouped by canonical family so a form
never contains two variants of one question. Selection uses a stored random seed (auditable, reproducible). If the
approved pool can't satisfy the request, generation fails honestly with the available count; it never silently
changes the test. The frozen form records versions, option permutations, marks, timing and the scoring policy.
"""

from __future__ import annotations

import hashlib
import json
import random
import secrets
import uuid
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from portal_api.errors import Conflict, NotFound, Unprocessable
from portal_api.modules.assessment.models import FormItem, PracticeForm
from portal_api.modules.content.models import Availability, ContentItem, ContentVersion
from portal_api.modules.curriculum.models import BookEdition, Chapter, Grade, Subject, Topic
from portal_api.modules.curriculum.regions import released_grade
from portal_api.modules.identity.deps import Principal

SELF_PACED_TOLERANCE_MS = 3000  # §10.5 default for self-paced timed practice; ranked mocks pin 0

Members = Sequence[tuple[Any, Any]]  # (item, published version) variants of one question family
Pick = tuple[uuid.UUID, Any, Any, list[str]]  # family, item, version, option display order


def variant(rng: random.Random, members: Members) -> tuple[Any, Any, list[str]]:
    """One variant of a family and its option order. Option IDs never change; only their display order does."""
    item, version = rng.choice(sorted(members, key=lambda iv: str(iv[0].id)))
    option_ids = [o["id"] for o in version.body["options"]]
    if version.body.get("shuffle_options", True):
        rng.shuffle(option_ids)
    return item, version, option_ids


def select_practice(pool: Mapping[uuid.UUID, Members], count: int, seed: int) -> list[Pick]:
    """The questions for a practice form: exactly `count` distinct families, reproducible from the stored seed and
    independent of pool order (GENERATOR-PROPERTIES-01). A short pool raises; the test is never quietly smaller."""
    if count > len(pool):
        raise ValueError(f"{len(pool)} families available, {count} requested")
    rng = random.Random(seed)  # noqa: S311 - reproducible sampling from a stored seed, not a secret
    return [(f, *variant(rng, pool[f])) for f in rng.sample(sorted(pool, key=str), count)]


def _pool(
    db: Session,
    grade: int,
    subject: str,
    chapter_ids: list[uuid.UUID],
    topic_ids: list[uuid.UUID],
    question_pool: str = "practice",
) -> dict[uuid.UUID, list[tuple[ContentItem, ContentVersion]]]:
    stmt = (
        select(ContentItem, ContentVersion)
        .join(ContentVersion, ContentVersion.id == ContentItem.published_version_id)
        .where(
            ContentItem.kind == "mcq",
            ContentItem.availability == Availability.live.value,  # quarantined/retired never count
            ContentItem.grade_number == grade,
            ContentItem.subject_code == subject,
            ContentItem.chapter_id.in_(chapter_ids),
        )
    )
    if question_pool != "any":  # P08.S3.T3: mock-reserved questions never reach practice tests
        stmt = stmt.where(ContentItem.question_pool == question_pool)
    if topic_ids:
        stmt = stmt.where(ContentItem.topic_id.in_(topic_ids))
    families: dict[uuid.UUID, list[tuple[ContentItem, ContentVersion]]] = defaultdict(list)
    for item, version in db.execute(stmt).all():
        if not passage_usable(db, version):
            continue  # its passage is no longer live (quarantined, retired): never shown without it
        families[item.family_id or item.id].append((item, version))
    return families


def passage_version(db: Session, version: ContentVersion) -> uuid.UUID | None:
    """PASSAGES-01: the live published version of the passage a question names (None without a live one)."""
    pid = version.body.get("passage_id") if isinstance(version.body, dict) else None
    if not pid:
        return None
    p = db.get(ContentItem, uuid.UUID(str(pid)))
    if p is None or p.availability != Availability.live.value:
        return None
    return p.published_version_id


def passage_usable(db: Session, version: ContentVersion) -> bool:
    """A question without a passage, or whose passage is live. Never show a question without its passage."""
    named = isinstance(version.body, dict) and bool(version.body.get("passage_id"))
    return not named or passage_version(db, version) is not None


def group_by_passage(picks: list[Pick]) -> list[Pick]:
    """Keep questions that share a passage next to each other, in the order each group first appears."""
    order: dict[object, int] = {}
    for i, (_, _, version, _) in enumerate(picks):
        key = version.body.get("passage_id") or f"solo-{i}"
        order.setdefault(key, i)
    return sorted(picks, key=lambda p: order[p[2].body.get("passage_id") or f"solo-{picks.index(p)}"])


def _book_chapters(db: Session, grade: int, subject: str) -> list[Chapter]:
    return list(
        db.scalars(
            select(Chapter)
            .join(BookEdition, BookEdition.id == Chapter.book_id)
            .join(Grade, Grade.id == BookEdition.grade_id)
            .join(Subject, Subject.id == BookEdition.subject_id)
            .where(
                Grade.number == grade,
                Subject.code == subject,
                Subject.active,
                Chapter.retired_at.is_(None),
                released_grade(),  # REGION-01
            )
            .order_by(Chapter.display_order)
        )
    )


def availability(db: Session, grade: int, subject: str) -> list[dict[str, Any]]:
    """Approved, published question families per chapter (counts only; nothing about the questions themselves)."""
    chapters = _book_chapters(db, grade, subject)
    if not chapters:
        raise NotFound("No book is available for this class and subject.")
    live = (
        ContentItem.kind == "mcq",
        ContentItem.availability == Availability.live.value,
        ContentItem.question_pool == "practice",
        ContentItem.grade_number == grade,
        ContentItem.subject_code == subject,
    )
    families = func.count(func.distinct(func.coalesce(ContentItem.family_id, ContentItem.id)))
    counts = {
        cid: int(n)
        for cid, n in db.execute(select(ContentItem.chapter_id, families).where(*live).group_by(ContentItem.chapter_id))
    }
    # P11.S3.T1 (PRACTICE-CONFIG-01): the topics a learner can narrow a chapter to, with their own counts. Only topics
    # with questions are listed; a test scoped to topics draws from exactly these (forms._pool).
    by_topic: dict[uuid.UUID, list[dict[str, Any]]] = defaultdict(list)
    rows = db.execute(
        select(Topic, families)
        .join(ContentItem, ContentItem.topic_id == Topic.id)
        .where(*live, Topic.retired_at.is_(None), Topic.chapter_id.in_([c.id for c in chapters]))
        .group_by(Topic.id)
        .order_by(Topic.display_order)
    ).all()
    for topic, n in rows:
        by_topic[topic.chapter_id].append(
            {"topic_id": topic.id, "number": topic.number, "title": topic.title, "questions": int(n)}
        )
    return [
        {
            "chapter_id": c.id,
            "number": c.number,
            "title": c.title,
            "questions": int(counts.get(c.id, 0)),
            "topics": by_topic.get(c.id, []),
        }
        for c in chapters
    ]


ESTIMATE_MIN_TESTS = 20  # fewer finished tests than this and no estimate is shown
ESTIMATE_WINDOW_DAYS = 180


def time_estimate(db: Session, grade: int, subject: str) -> tuple[int | None, int]:
    """P11.S3.T1 (PRACTICE-CONFIG-01): a measured time per question, never a guess. The median of how long learners
    actually took per question on untimed practice tests they submitted in this class and subject over the last 180
    days (ignoring per-question times under 5 seconds or over 30 minutes, which are not answering). Returns (seconds per
    question or None, tests measured); None until at least ESTIMATE_MIN_TESTS tests exist."""
    from datetime import timedelta

    from sqlalchemy import Float, cast, literal

    from portal_api.modules.assessment.models import Attempt

    per_question = (
        cast(func.extract("epoch", Attempt.finalised_at - Attempt.started_at), Float) / PracticeForm.question_count
    )
    stmt = (
        select(func.percentile_cont(literal(0.5)).within_group(per_question), func.count())
        .select_from(Attempt)
        .join(PracticeForm, PracticeForm.id == Attempt.form_id)
        .where(
            PracticeForm.kind == "practice",
            PracticeForm.duration_s.is_(None),
            PracticeForm.grade_number == grade,
            PracticeForm.subject_code == subject,
            Attempt.finalise_reason == "manual",
            Attempt.finalised_at.is_not(None),
            Attempt.finalised_at > func.now() - timedelta(days=ESTIMATE_WINDOW_DAYS),
            per_question.between(5, 1800),
        )
    )
    median, tests = db.execute(stmt).one()
    tests = int(tests or 0)
    if tests < ESTIMATE_MIN_TESTS or median is None:
        return None, tests
    return max(5, round(float(median))), tests


def _request_hash(req: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(req, sort_keys=True, default=str).encode()).hexdigest()


def create_form(
    db: Session,
    who: Principal,
    *,
    idempotency_key: str,
    grade: int,
    subject: str,
    chapter_ids: list[uuid.UUID],
    topic_ids: list[uuid.UUID],
    question_count: int,
    timed_minutes: int | None,
    feedback_mode: str,
    scope_mode: str = "chapters",
    half: int | None = None,
    mix: list[tuple[str, int]] | None = None,
) -> PracticeForm:
    req: dict[str, Any] = {
        "grade": grade,
        "subject": subject,
        "scope": scope_mode,
        "half": half,
        "chapter_ids": sorted(map(str, chapter_ids)),
        "topic_ids": sorted(map(str, topic_ids)),
        "question_count": question_count,
        "timed_minutes": timed_minutes,
        "feedback_mode": feedback_mode,
    }
    if scope_mode == "multi_subject":  # only then, so earlier request hashes stay valid for idempotent retries
        req["mix"] = [list(m) for m in mix or []]
    rhash = _request_hash(req)
    existing = db.scalar(
        select(PracticeForm).where(
            PracticeForm.owner_id == who.user.id, PracticeForm.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        if existing.request_hash != rhash:
            raise Conflict("This request key was already used for a different test.")
        return existing

    from portal_api.modules.access import service as access

    subjects = [s for s, _ in mix or []] if scope_mode == "multi_subject" and mix else [subject]
    access.require_access(db, who.user.id, purpose="Practice tests", need=access.Need.subjects(grade, *subjects))
    if scope_mode == "multi_subject":
        seed, chosen, scope = _multi_subject(db, grade, mix or [], question_count, chapter_ids, topic_ids, half)
        subject = mix[0][0] if mix else subject
    else:
        seed, chosen, scope = _single_subject(
            db, grade, subject, scope_mode, half, chapter_ids, topic_ids, question_count
        )
    form = PracticeForm(
        id=uuid.uuid4(),
        owner_id=who.user.id,
        idempotency_key=idempotency_key,
        request_hash=rhash,
        kind="practice",
        grade_number=grade,
        subject_code=subject,
        scope=scope,
        seed=seed,
        question_count=question_count,
        duration_s=timed_minutes * 60 if timed_minutes else None,
        late_write_tolerance_ms=SELF_PACED_TOLERANCE_MS if timed_minutes else 0,
        feedback_mode=feedback_mode,
        negative_marks=0,
        invalid_item_treatment="EXCLUDE",
    )
    return _freeze(db, who, form, chosen, idempotency_key, rhash)


def _multi_subject(
    db: Session,
    grade: int,
    mix: list[tuple[str, int]],
    question_count: int,
    chapter_ids: list[uuid.UUID],
    topic_ids: list[uuid.UUID],
    half: int | None,
) -> tuple[int, list[Pick], dict[str, Any]]:
    """P09.S1.T3 (MULTI-SUBJECT-01): custom practice from several subjects' whole books in one class (classes are
    never mixed), per-subject counts in the learner's order. Labelled custom practice, never an official pattern."""
    from portal_api.modules.assessment import mocks

    if chapter_ids or topic_ids or half:
        raise Unprocessable("A custom mix uses each subject's whole book; don't choose chapters or topics.")
    subjects = [s for s, _ in mix]
    if not 2 <= len(mix) <= 5 or len(set(subjects)) != len(subjects):
        raise Unprocessable("Choose two to five different subjects for a custom mix.")
    if sum(n for _, n in mix) != question_count:
        raise Unprocessable("The subjects' question counts must add up to the test's question count.")
    pools = []
    for s, n in mix:
        book = _book_chapters(db, grade, s)
        if not book:
            raise Unprocessable(f"{s} isn't a subject with a book in this class.")
        pools.append((n, _pool(db, grade, s, [c.id for c in book], [])))
    short = [
        {"subject": s, "grades": [grade], "required": n, "available": len(p)}
        for (s, n), (_, p) in zip(mix, pools, strict=True)
        if len(p) < n
    ]
    if short:
        raise Unprocessable(
            "There aren't enough approved questions for this mix yet; lower the count for these subjects.",
            code_reason="POOL_SHORTAGE",
            sections=short,
        )
    seed = secrets.randbits(62)
    picked = mocks.select_sections(pools, set(), seed)
    sections, position = [], 0
    for s, n in mix:
        sections.append({"subject": s, "grades": [grade], "from": position + 1, "to": position + n})
        position += n
    scope = {"mode": "multi_subject", "grades": [grade], "question_pool": "practice", "sections": sections}
    return seed, [p for picks, _ in picked for p in picks], scope


def _single_subject(
    db: Session,
    grade: int,
    subject: str,
    scope_mode: str,
    half: int | None,
    chapter_ids: list[uuid.UUID],
    topic_ids: list[uuid.UUID],
    question_count: int,
) -> tuple[int, list[Pick], dict[str, Any]]:
    grades = [11, 12] if scope_mode == "combined" else [grade]
    book = _book_chapters(db, grade, subject)
    if scope_mode != "chapters" and topic_ids:
        raise Unprocessable("Topics can only be chosen for a chapter test.")
    if scope_mode == "full_book":
        chapter_ids = [c.id for c in book]
    elif scope_mode == "half_book":
        if half not in (1, 2):
            raise Unprocessable("Choose the first or second half of the book.")
        split = (len(book) + 1) // 2  # by the book's own chapter order, never by page numbers
        chapter_ids = [c.id for c in (book[:split] if half == 1 else book[split:])]
    elif scope_mode == "combined":
        chapter_ids = [c.id for g in grades for c in _book_chapters(db, g, subject)]
    valid = {c.id for g in grades for c in _book_chapters(db, g, subject)}
    if not chapter_ids or not set(chapter_ids) <= valid:
        raise Unprocessable("Choose chapters from this class and subject's book.")
    if topic_ids:
        topics = db.scalars(select(Topic).where(Topic.id.in_(topic_ids), Topic.retired_at.is_(None))).all()
        if len(topics) != len(set(topic_ids)) or any(t.chapter_id not in set(chapter_ids) for t in topics):
            raise Unprocessable("Topics must belong to the chosen chapters.")
    pool: dict[uuid.UUID, list[tuple[ContentItem, ContentVersion]]] = {}
    for g in grades:
        pool.update(_pool(db, g, subject, chapter_ids, topic_ids))
    if len(pool) < question_count:
        raise Unprocessable(
            f"Only {len(pool)} approved question(s) are available for this selection; {question_count} were requested.",
            available=len(pool),
            requested=question_count,
        )

    seed = secrets.randbits(62)
    scope = {
        "mode": scope_mode,
        "grades": grades,
        "half": half,
        "chapter_ids": sorted(map(str, chapter_ids)),
        "topic_ids": sorted(map(str, topic_ids)),
    }
    return seed, select_practice(pool, question_count, seed), scope


def _freeze(
    db: Session, who: Principal, form: PracticeForm, chosen: list[Pick], idempotency_key: str, rhash: str
) -> PracticeForm:
    db.add(form)
    for position, (family, item, version, option_ids) in enumerate(group_by_passage(chosen), start=1):
        pv = passage_version(db, version)
        db.add(
            FormItem(
                form_id=form.id,
                position=position,
                item_id=item.id,
                family_id=family,
                version_id=version.id,
                marks=int(version.body.get("marks", 1)),
                option_order=option_ids,
                grade_number=item.grade_number,
                subject_code=item.subject_code,
                passage_version_id=pv or None,
            )
        )
    try:
        db.commit()
    except IntegrityError:  # a concurrent request with the same key won; return its form
        db.rollback()
        winner = db.scalar(
            select(PracticeForm).where(
                PracticeForm.owner_id == who.user.id, PracticeForm.idempotency_key == idempotency_key
            )
        )
        if winner is None or winner.request_hash != rhash:
            raise Conflict("This request key was already used for a different test.") from None
        return winner
    db.refresh(form)
    return form


def learner_items(db: Session, form: PracticeForm) -> list[dict[str, Any]]:
    """Keyless snapshot: stems and options in the frozen order. Never includes keys or explanations."""
    out: list[dict[str, Any]] = []
    for fi in form.items:
        version = db.get(ContentVersion, fi.version_id)
        assert version is not None
        options = {o["id"]: o for o in version.body["options"]}
        out.append(
            {
                "position": fi.position,
                "marks": fi.marks,
                "stem": version.body["stem"],
                "options": [{"id": oid, "blocks": options[oid]["blocks"]} for oid in fi.option_order],
                "passage": passage_snapshot(db, fi),
            }
        )
    return out


def passage_snapshot(db: Session, fi: FormItem) -> dict[str, Any] | None:
    """The pinned passage shown with a question (PASSAGES-01); a later passage revision never changes a test."""
    if fi.passage_version_id is None:
        return None
    pv = db.get(ContentVersion, fi.passage_version_id)
    return {"id": str(pv.item_id), "blocks": pv.body.get("blocks", [])} if pv is not None else None


def superseded_positions(db: Session, form: PracticeForm) -> list[int]:
    """Positions whose frozen question version is no longer the live published version (quarantined, retired,
    corrected or replaced since the form was built)."""
    out = []
    for fi in form.items:
        item = db.get(ContentItem, fi.item_id)
        if item is None or item.availability != Availability.live.value or item.published_version_id != fi.version_id:
            out.append(fi.position)
    return out


def _position_pool(db: Session, form: PracticeForm, position: int) -> Mapping[uuid.UUID, Members]:
    """The approved pool a position was drawn from: the form's chapters/topics, or its mock section."""
    scope = form.scope or {}
    if scope.get("sections"):  # mocks and multi-subject custom practice draw per section
        from portal_api.modules.assessment import mocks

        section = next(s for s in scope["sections"] if int(s["from"]) <= position <= int(s["to"]))
        return mocks._section_pool(db, section["subject"], section["grades"], scope.get("question_pool", "mock"))
    chapters = [uuid.UUID(c) for c in scope.get("chapter_ids", [])]
    topics = [uuid.UUID(t) for t in scope.get("topic_ids", [])]
    pool: dict[uuid.UUID, list[tuple[ContentItem, ContentVersion]]] = {}
    for g in scope.get("grades", [form.grade_number]):
        pool.update(_pool(db, int(g), form.subject_code, chapters, topics))
    return pool


def replace_superseded(db: Session, form: PracticeForm) -> bool:
    """§5.7 before start (FORM-REPLACE-01): swap each superseded question of an unstarted form for an approved one
    from the same pool (a corrected version of the same question counts), keeping one question per family, the
    section blueprint and the form's marks policy. Reproducible from the form seed and logged in `scope.replaced`.
    All or nothing: returns False, changing nothing, when any position has no replacement. Callers hold the form
    lock and have checked that no attempt exists."""
    from portal_api.modules.assessment.mocks import _seen_families

    positions = superseded_positions(db, form)
    if not positions:
        return True
    by_position = {fi.position: fi for fi in form.items}
    taken = {fi.family_id for fi in form.items if fi.position not in positions}
    seen = _seen_families(db, form.owner_id) if form.kind == "mock" else set()
    log = []
    swaps = []
    for position in sorted(positions):
        fi = by_position[position]
        pool = _position_pool(db, form, position)
        free = sorted((f for f in pool if f not in taken), key=lambda f: (f != fi.family_id, f in seen, str(f)))
        if not free:
            return False
        rng = random.Random(f"{form.seed}:replace:{position}:{fi.version_id}")  # noqa: S311 - reproducible, not secret
        same = [f for f in free if f == fi.family_id]  # a corrected version of the same question comes first
        unseen = [f for f in free if f not in seen]
        family = same[0] if same else rng.choice(unseen or free)
        item, version, option_ids = variant(rng, pool[family])
        taken.add(family)
        swaps.append((fi, family, item, version, option_ids))
        log.append(
            {
                "position": position,
                "from_version": str(fi.version_id),
                "to_version": str(version.id),
                "reason": "superseded",
            }
        )
    for fi, family, item, version, option_ids in swaps:  # the families are distinct: no unique-constraint clash
        fi.family_id, fi.item_id, fi.version_id, fi.option_order = family, item.id, version.id, option_ids
        fi.grade_number, fi.subject_code = item.grade_number, item.subject_code
        fi.passage_version_id = passage_version(db, version)
        if form.kind != "mock":  # mocks keep the profile's marks per question
            fi.marks = int(version.body.get("marks", 1))
    form.scope = {**(form.scope or {}), "replaced": [*(form.scope or {}).get("replaced", []), *log]}
    db.flush()
    return True


def item_keys(db: Session, form: PracticeForm) -> dict[int, dict[str, Any]]:
    """Frozen keys and explanations per position. Server-side only: scoring and post-release review."""
    out: dict[int, dict[str, Any]] = {}
    for fi in form.items:
        version = db.get(ContentVersion, fi.version_id)
        assert version is not None
        out[fi.position] = {
            "correct_option_id": version.body["correct_option_id"],
            "option_ids": tuple(fi.option_order),
            "marks": fi.marks,
            "explanation": version.body.get("explanation", {}),
            "stem": version.body["stem"],
            "options": {o["id"]: o for o in version.body["options"]},
        }
    return out
