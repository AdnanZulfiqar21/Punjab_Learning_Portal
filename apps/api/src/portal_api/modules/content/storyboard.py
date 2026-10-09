"""Scene-by-scene video storyboards (roadmap P07.S4.T1/T2; STORYBOARD-01).

A storyboard is a production record, never shown to learners. It holds:

* the lesson outcome, learning objective, prerequisites and target duration;
* ordered scenes. Each scene has a stable ID and a contiguous time window, the visual, on-screen text, narration,
  transition, equations, assets and accessibility notes, plus the factual **claims** it teaches. Every claim cites
  one of the version's source page references, so teaching constraints stay separate from creative direction;
* creative direction for the whole video.

Drafts may be incomplete. Submission and publication need a complete, internally consistent storyboard in which every
claim cites a source. A storyboard is exported as a prompt package for a production tool. Generated media is never
published from generation success alone (P07.S4.T3).
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from portal_api.modules.content import blocks

SCENE_ID = r"^[a-z0-9][a-z0-9_-]{0,19}$"
REVIEW_CHECKLIST = ("accuracy", "sources", "pacing", "accessibility", "rights")
EMPTY_BODY: dict[str, Any] = {
    "objective": "",
    "outcome": "",
    "prerequisites": [],
    "duration_s": None,
    "creative_direction": "",
    "scenes": [],
}

Text = Annotated[str, Field(max_length=4000)]


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: Annotated[str, Field(min_length=1, max_length=500)]
    source_ref: int = Field(ge=0, le=49, description="Index into this version's source page references")


class Scene(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Annotated[str, Field(pattern=SCENE_ID)]
    start_s: int = Field(ge=0, le=7200)
    end_s: int = Field(ge=1, le=7200)
    visual: Annotated[str, Field(max_length=2000)] = ""
    on_screen_text: Annotated[str, Field(max_length=500)] = ""
    narration: Text = ""
    transition: Annotated[str, Field(max_length=200)] = ""
    equations: list[Annotated[str, Field(max_length=300)]] = Field(default_factory=list, max_length=10)
    assets: list[Annotated[str, Field(max_length=300)]] = Field(default_factory=list, max_length=20)
    accessibility: Annotated[str, Field(max_length=1000)] = ""
    claims: list[Claim] = Field(default_factory=list, max_length=20)


class StoryboardBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    objective: Annotated[str, Field(max_length=500)] = ""
    outcome: Annotated[str, Field(max_length=500)] = ""
    prerequisites: list[Annotated[str, Field(max_length=300)]] = Field(default_factory=list, max_length=10)
    duration_s: int | None = Field(default=None, ge=10, le=7200)
    creative_direction: Annotated[str, Field(max_length=2000)] = ""
    scenes: list[Scene] = Field(default_factory=list, max_length=60)


def parse(body: object) -> tuple[StoryboardBody | None, list[str]]:
    try:
        return StoryboardBody.model_validate(body), []
    except ValidationError as e:
        return None, [f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()]


def validate(body: object, for_publication: bool) -> blocks.Validation:
    sb, errors = parse(body)
    warnings: list[str] = []
    if sb is None:
        return blocks.Validation(errors=errors, warnings=[], block_types=[])
    ids = [s.id for s in sb.scenes]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        errors.append(f"Scene IDs must be unique: {', '.join(dupes)}.")
    expected = 0
    for n, s in enumerate(sb.scenes, start=1):
        if s.end_s <= s.start_s:
            errors.append(f"Scene {n} ({s.id}) must end after it starts.")
        if s.start_s != expected:
            errors.append(f"Scene {n} ({s.id}) should start at {expected}s so the scenes are continuous.")
        expected = s.end_s
    if sb.duration_s is not None and sb.scenes and expected != sb.duration_s:
        warnings.append(f"The scenes run to {expected}s but the target duration is {sb.duration_s}s.")
    # Drafts are only parsed; validation runs at submission and publication, and both need a complete storyboard.
    if not sb.objective.strip():
        errors.append("Add the learning objective.")
    if not sb.outcome.strip():
        errors.append("Add the lesson outcome.")
    if not sb.scenes:
        errors.append("Add at least one scene.")
    for n, s in enumerate(sb.scenes, start=1):
        if not s.narration.strip():
            errors.append(f"Scene {n} ({s.id}) needs narration.")
        if not s.visual.strip():
            errors.append(f"Scene {n} ({s.id}) needs a visual description.")
        if (s.equations or s.visual.strip()) and not s.accessibility.strip():
            errors.append(f"Scene {n} ({s.id}) needs accessibility notes (describe visuals and equations).")
    if not any(s.claims for s in sb.scenes):
        errors.append("Link the factual claims the video teaches to source pages.")
    return blocks.Validation(errors=errors, warnings=warnings, block_types=[])


def claim_errors(body: object, source_refs: list[dict[str, Any]]) -> list[str]:
    """Every claim must cite one of this version's source references (checked with the version's refs)."""
    sb, _ = parse(body)
    if sb is None:
        return []
    return [
        f"Scene {s.id}: claim {k} cites source reference {c.source_ref + 1}, which doesn't exist."
        for s in sb.scenes
        for k, c in enumerate(s.claims, start=1)
        if c.source_ref >= len(source_refs)
    ]


def parse_draft(body: object) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    sb, errors = parse(body)
    if sb is None:
        return None, errors, []
    return sb.model_dump(mode="json"), [], []
