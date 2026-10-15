"""Duplicate and near-identical question detection (roadmap P08.S3.T1; DUP-STEMS-01).

A question's signature is its canonical text: the stem with the options (multiple choice) or the subparts (written),
lower-cased with punctuation and spacing folded, from `blocks.text_of`. Another question of the same kind, class and
subject in a different family whose signature is identical is reported as an exact duplicate; one at least
`NEAR_RATIO` alike (after a cheap word-overlap filter) as near-identical. Variants of one family are expected to be
alike and are never reported.

Both are warnings for the academic reviewer, shown when an item is submitted, reviewed or published: whether two
questions are the same, a variant or legitimately different is an academic decision, and the reviewed answer is to
make one a variant of the other's family or to change it. Nothing is merged or blocked automatically.

It compares in Python against the class and subject's other questions (their published version, or the working one
before publication). That is enough for banks of a few thousand questions per class and subject; a trigram index
(`pg_trgm`) is the path if banks grow far beyond that.
"""

from __future__ import annotations

import re
import uuid
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from portal_api.modules.content import blocks
from portal_api.modules.content.models import Availability, ContentItem, ContentVersion

QUESTION_KINDS = ("mcq", "written")
NEAR_RATIO = 0.9
_WORD_OVERLAP = 0.6  # a cheap first filter before the character-level comparison
_FOLD = re.compile(r"[^\w]+", re.UNICODE)


def _parsed(block_list: object) -> list[Any]:
    parsed, _ = blocks.parse({"blocks": block_list if isinstance(block_list, list) else []})
    return list(parsed.blocks) if parsed is not None else []


def signature(kind: str, body: object) -> str:
    """The question's canonical text ('' when there is no stem yet)."""
    if not isinstance(body, dict):
        return ""
    parts = [blocks.text_of(_parsed(body.get("stem")))]
    if kind == "mcq":
        parts += sorted(
            blocks.text_of(_parsed(o.get("blocks"))) for o in body.get("options") or [] if isinstance(o, dict)
        )
    elif kind == "written":
        parts += [blocks.text_of(_parsed(s.get("blocks"))) for s in body.get("subparts") or [] if isinstance(s, dict)]
    text = " | ".join(p for p in parts if p)
    return " ".join(_FOLD.sub(" ", text.lower()).split())


def _alike(a: str, b: str) -> bool:
    if not a or not b or min(len(a), len(b)) / max(len(a), len(b)) < NEAR_RATIO:
        return False
    wa, wb = set(a.split()), set(b.split())
    if len(wa & wb) / max(1, len(wa | wb)) < _WORD_OVERLAP:
        return False
    return SequenceMatcher(None, a, b, autojunk=False).ratio() >= NEAR_RATIO


def find(db: Session, item: ContentItem, version: ContentVersion) -> list[str]:
    """Warnings naming the other questions this one duplicates or nearly duplicates."""
    if item.kind not in QUESTION_KINDS:
        return []
    mine = signature(item.kind, version.body)
    if not mine:
        return []
    others = db.execute(
        select(ContentItem.id, ContentItem.title, ContentItem.family_id, ContentVersion.body)
        .join(ContentVersion, ContentVersion.id == ContentItem.published_version_id)
        .where(
            ContentItem.kind == item.kind,
            ContentItem.grade_number == item.grade_number,
            ContentItem.subject_code == item.subject_code,
            ContentItem.id != item.id,
            ContentItem.availability != Availability.retired.value,
        )
    ).all()
    drafts = db.execute(
        select(ContentItem.id, ContentItem.title, ContentItem.family_id, ContentVersion.body)
        .join(ContentVersion, ContentVersion.id == ContentItem.working_version_id)
        .where(
            ContentItem.kind == item.kind,
            ContentItem.grade_number == item.grade_number,
            ContentItem.subject_code == item.subject_code,
            ContentItem.id != item.id,
            ContentItem.published_version_id.is_(None),
            ContentItem.availability != Availability.retired.value,
        )
    ).all()
    family = item.family_id or item.id
    warnings = []
    for other_id, title, other_family, body in [*others, *drafts]:
        if (other_family or other_id) == family:
            continue  # a variant of the same question is meant to be alike
        theirs = signature(item.kind, body)
        if theirs == mine:
            warnings.append(
                f"This question's text and answers match '{title}' ({_short(other_id)}) exactly. An academic reviewer "
                "should decide whether it is a duplicate (make it a variant of that question, or change it)."
            )
        elif _alike(mine, theirs):
            warnings.append(
                f"This question is nearly identical to '{title}' ({_short(other_id)}). An academic reviewer should "
                "decide whether they are the same question, a variant or two different questions."
            )
    return warnings


def _short(item_id: uuid.UUID) -> str:
    return str(item_id)[:8]
