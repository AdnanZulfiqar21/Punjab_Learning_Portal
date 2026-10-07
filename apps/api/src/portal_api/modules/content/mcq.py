"""Single-best-answer MCQ content (roadmap P08.S1/P08.S2).

A question version stores its stem, ordered options with **stable option IDs**, the correct option, marks, explanations
(correct reasoning, per-distractor notes, worked steps), source pages, quality metadata and an origin label. Drafts may
be incomplete; submission requires a complete, internally consistent question with a finished explanation.

Answer keys and explanations are academic secrets until release: nothing in this module is served to learners. Exam
payloads are built from frozen form snapshots that omit `correct_option_id` and `explanation` (P08.S2.T3).
"""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from portal_api.modules.content import blocks
from portal_api.modules.content.blocks import Block as ContentBlock  # avoid clashing with fields named `blocks`

OPTION_ID = r"^[a-z][a-z0-9_-]{0,11}$"
MIN_OPTIONS, MAX_OPTIONS = 2, 6

# Options whose meaning depends on their position or on other options; shuffling them changes the question.
_DEPENDENT = re.compile(r"\b(all|none|both|neither) of (the )?(above|these|them)\b|\b(a|b|c|d) and (a|b|c|d)\b", re.I)


class Option(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Annotated[str, Field(pattern=OPTION_ID)]
    blocks: list[ContentBlock] = Field(default_factory=list, max_length=10)


class Explanation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    correct: list[ContentBlock] = Field(default_factory=list, max_length=40)
    distractors: dict[str, Annotated[str, Field(max_length=2000)]] = Field(default_factory=dict)
    worked_steps: list[ContentBlock] = Field(default_factory=list, max_length=40)


class Metadata(BaseModel):
    """Editorial estimates only. Empirical difficulty/discrimination are computed separately later (P08.S4.T3)."""

    model_config = ConfigDict(extra="forbid")
    difficulty: Literal["easy", "medium", "hard"] | None = None
    estimated_seconds: int | None = Field(default=None, ge=10, le=1800)
    cognitive_demand: Literal["recall", "understand", "apply", "analyse"] | None = None
    misconceptions: list[Annotated[str, Field(max_length=300)]] = Field(default_factory=list, max_length=10)


class PastPaper(BaseModel):
    model_config = ConfigDict(extra="forbid")
    board: Annotated[str, Field(min_length=2, max_length=120)]
    year: int = Field(ge=1990, le=2100)
    paper: Annotated[str, Field(max_length=120)] | None = None
    authorisation_ref: Annotated[str, Field(min_length=5, max_length=300)]  # where reuse permission is recorded


class MCQBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stem: list[ContentBlock] = Field(default_factory=list, max_length=40)
    options: list[Option] = Field(default_factory=list, max_length=MAX_OPTIONS)
    correct_option_id: Annotated[str, Field(pattern=OPTION_ID)] | None = None
    marks: int = Field(default=1, ge=1, le=10)
    shuffle_options: bool = True
    explanation: Explanation = Field(default_factory=Explanation)
    metadata: Metadata = Field(default_factory=Metadata)
    origin: Literal["original_practice", "authorised_past_paper"] = "original_practice"
    past_paper: PastPaper | None = None
    language: Literal["en", "ur"] = "en"


_adapter = TypeAdapter(MCQBody)

EMPTY_BODY: dict[str, object] = {
    "stem": [],
    "options": [{"id": f"o{i}", "blocks": []} for i in range(1, 5)],
    "correct_option_id": None,
}


def parse(body: object) -> tuple[MCQBody | None, list[str]]:
    try:
        return _adapter.validate_python(body), []
    except ValidationError as e:
        return None, [f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors()]


def all_blocks(q: MCQBody) -> list[tuple[str, list[ContentBlock]]]:
    out: list[tuple[str, list[ContentBlock]]] = [("stem", q.stem)]
    out += [(f"options[{o.id}]", o.blocks) for o in q.options]
    out += [("explanation.correct", q.explanation.correct), ("explanation.worked_steps", q.explanation.worked_steps)]
    return out


def block_types(q: MCQBody) -> list[str]:
    return sorted({b.type for _, bl in all_blocks(q) for b in bl})


def validate(body: object, *, for_publication: bool) -> blocks.Validation:
    """Submission rules (and, for publication, renderer compatibility). Drafts are saved without these checks."""
    q, errors = parse(body)
    if q is None:
        return blocks.Validation(errors, [], [])
    warnings: list[str] = []
    if not q.stem:
        errors.append("Write the question stem.")
    ids = [o.id for o in q.options]
    if not MIN_OPTIONS <= len(q.options) <= MAX_OPTIONS:
        errors.append(f"A question needs {MIN_OPTIONS} to {MAX_OPTIONS} options.")
    if len(set(ids)) != len(ids):
        errors.append("Option IDs must be unique.")
    texts: dict[str, str] = {}
    for o in q.options:
        if not o.blocks:
            errors.append(f"Option {o.id} is empty.")
            continue
        t = blocks.text_of(o.blocks)
        if t in texts.values():
            errors.append(f"Option {o.id} duplicates another option.")
        texts[o.id] = t
    if q.correct_option_id is None:
        errors.append("Mark the correct option.")
    elif q.correct_option_id not in ids:
        errors.append("The correct option must be one of the options.")
    if not q.explanation.correct:
        errors.append("Explain why the correct answer is correct (unfinished explanations can't be submitted).")
    stray = set(q.explanation.distractors) - set(ids)
    if stray:
        errors.append(f"Distractor notes refer to unknown options: {', '.join(sorted(stray))}.")
    if q.correct_option_id in q.explanation.distractors:
        errors.append("The correct option can't have a distractor note.")
    if q.origin == "authorised_past_paper" and q.past_paper is None:
        errors.append("Past-paper questions need the board, year and where reuse is authorised.")
    if q.origin == "original_practice" and q.past_paper is not None:
        errors.append("Original practice questions must not carry past-paper details.")
    if q.shuffle_options and any(_DEPENDENT.search(t) for t in texts.values()):
        warnings.append(
            "An option refers to other options (e.g. 'all of the above'); turn off shuffling so its meaning is kept."
        )
    missing_notes = [i for i in ids if i != q.correct_option_id and i not in q.explanation.distractors]
    if missing_notes and q.correct_option_id in ids:
        warnings.append(f"No distractor note for: {', '.join(missing_notes)}.")
    for where, bl in all_blocks(q):
        r_err, r_warn = blocks.check_renderers(bl, for_publication=for_publication, where=where)
        errors += r_err
        warnings += r_warn
    return blocks.Validation(errors, warnings, block_types(q))


# Reviewers confirm each check before approving a question (P08.S2.T1).
REVIEW_CHECKLIST = ("accuracy", "ambiguity", "units", "diagrams", "grammar", "mapping")
