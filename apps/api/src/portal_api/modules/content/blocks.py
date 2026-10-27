"""Content block schema and renderer capability registry (roadmap §5.4).

Every content version stores `content_schema_version` and the block types it uses. Each block type declares the minimum
renderer version per platform and whether a reviewed fallback is mandatory. Publication is rejected when a block needs
a renderer newer than the oldest supported client and no reviewed fallback is attached (§5.4 rule 4).

All text is plain text: nothing is interpreted as HTML or markup, and clients render it as text (P07.S1.T1).
Scientific notation keeps an accessible equivalent: equations carry `text_alt`, diagrams `alt` (and an optional long
description), tables a caption.

Blocks hold the author's own explanatory text. They never embed textbook page images or long verbatim passages; source
material is referenced by page (`source_refs`), not copied (IMPL-01).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, model_validator

CONTENT_SCHEMA_VERSION = 1
PLATFORMS = ("web", "android", "ios")

# Oldest renderer version each platform's supported clients understand, as the code knows it: the lower bound used for
# any supported build that has no registered capability manifest. With manifests registered, publication and previews
# use the oldest supported build's own manifest instead (`clients.renderer_floor`, CLIENT-FLOOR-01).
SUPPORTED_RENDERER: dict[str, int] = {"web": 1, "android": 1, "ios": 1}
_FLOOR: ContextVar[dict[str, int] | None] = ContextVar("renderer_floor", default=None)


def supported_renderer() -> dict[str, int]:
    """The renderer versions the oldest supported clients understand, for the current check."""
    return _FLOOR.get() or SUPPORTED_RENDERER


@contextmanager
def client_floor(values: dict[str, int]) -> Iterator[None]:
    """Check blocks against these renderer versions (from the registered build manifests) within this block."""
    token = _FLOOR.set(values)
    try:
        yield
    finally:
        _FLOOR.reset(token)


@dataclass(frozen=True)
class BlockSpec:
    type: str
    version: int
    min_renderer: dict[str, int]
    fallback_required_below: bool  # a reviewed fallback is mandatory where a supported client is older than min
    description: str


REGISTRY: dict[str, BlockSpec] = {
    s.type: s
    for s in (
        BlockSpec("heading", 1, {"web": 1, "android": 1, "ios": 1}, True, "Section heading (level 2 or 3)."),
        BlockSpec("paragraph", 1, {"web": 1, "android": 1, "ios": 1}, True, "Plain explanatory text."),
        BlockSpec("list", 1, {"web": 1, "android": 1, "ios": 1}, True, "Ordered or unordered list."),
        BlockSpec("callout", 1, {"web": 1, "android": 1, "ios": 1}, True, "Definition, tip, note or warning box."),
        BlockSpec("table", 1, {"web": 1, "android": 1, "ios": 1}, True, "Small data table with a caption."),
        # Equations need a typeset renderer. The web typesets them (P01.S4.T2, RENDERER-SPIKE-01); the apps don't yet,
        # so every equation still needs a reviewed static rendering plus its text equivalent before it can be published.
        BlockSpec("equation", 1, {"web": 2, "android": 2, "ios": 2}, True, "LaTeX equation with text equivalent."),
        # P07.S1.T3: formative only. Renderer v1 includes it on every platform because no native build had shipped when
        # it was added (B07); after a store release, a new block type must raise the renderer version instead.
        BlockSpec("checkpoint", 1, {"web": 1, "android": 1, "ios": 1}, True, "Formative question or self-check."),
        # P07.S1.T1 (LESSON-BLOCKS-01): like checkpoints, these join renderer v1 because no native build has shipped
        # (B07). After the first store release a new block type must raise the renderer version instead.
        BlockSpec("example", 1, {"web": 1, "android": 1, "ios": 1}, True, "Worked example: problem, steps, answer."),
        BlockSpec("diagram", 1, {"web": 1, "android": 1, "ios": 1}, True, "Archived image with alt text and caption."),
        BlockSpec("handout", 1, {"web": 1, "android": 1, "ios": 1}, True, "Downloadable archived PDF handout."),
        # Constrained original scenes (TOPIC-READER-01). Geometry lives in the app, not in a downloaded script.
        # A still diagram in the same lesson is the readable fallback if the scene cannot start.
        BlockSpec(
            "scene", 1, {"web": 1, "android": 1, "ios": 1}, True, "Named original scene with a text alternative."
        ),
        # Biology XI pilot (MODEL3D-01): an original 3D model rendered to archived stills. Renderer 2 shows the poster
        # and a drag-to-turn sequence of stills (native) or the live scene (web). Older clients show the reviewed
        # fallback image, which every model3d block must carry.
        BlockSpec(
            "model3d", 1, {"web": 2, "android": 2, "ios": 2}, True, "Original 3D model: poster, turntable stills."
        ),
    )
}


class _Block(BaseModel):
    model_config = ConfigDict(extra="forbid")
    v: Literal[1] = 1


class Fallback(BaseModel):
    """Reviewed fallback for clients that can't render a block natively (§5.4 rule 4)."""

    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=2000)
    image_asset_id: str | None = Field(default=None, max_length=80)  # static vector/raster rendering (P07 assets)
    alt: str | None = Field(default=None, max_length=500)
    reviewed: bool = False


Text = Annotated[str, Field(min_length=1, max_length=5000)]
Short = Annotated[str, Field(min_length=1, max_length=300)]
# BOOK-CORRECTION-01: the English lesson keeps the textbook's printed wording, errors included. `book_errors` names the
# exact printed passages that are wrong; clients mark them in red, and a `correction` callout after the block gives the
# right version. Each passage must occur in the block's own text.
BookErrors = Annotated[list[Short] | None, Field(max_length=10)]
# An archived asset version (ASSETS-01). Which kind, class and subject it must be is checked against the archive.
AssetRef = Annotated[str, Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")]


class _Marked(_Block):
    """A block whose text can carry book-error marks (BOOK-CORRECTION-01)."""

    book_errors: BookErrors = None  # absent, not empty, so stored bodies stay as authored (dumps drop None)

    def _texts(self) -> list[str]:
        raise NotImplementedError

    @model_validator(mode="after")
    def _marks_in_text(self) -> _Marked:
        texts = self._texts()
        for mark in self.book_errors or []:
            if not any(mark in t for t in texts):
                raise ValueError(f"book error {mark!r} does not occur in the block's text")
        return self


class Heading(_Marked):
    type: Literal["heading"]
    level: Literal[2, 3] = 2
    text: Short

    def _texts(self) -> list[str]:
        return [self.text]


class Paragraph(_Marked):
    type: Literal["paragraph"]
    text: Text

    def _texts(self) -> list[str]:
        return [self.text]


class ListBlock(_Marked):
    type: Literal["list"]
    ordered: bool = False
    items: list[Annotated[str, Field(min_length=1, max_length=1000)]] = Field(min_length=1, max_length=50)

    def _texts(self) -> list[str]:
        return list(self.items)


class Callout(_Marked):
    type: Literal["callout"]
    # `correction`: the right version of a book error marked in the block before it (BOOK-CORRECTION-01). A printed
    # box (Do You Know, For Your Information) may itself carry marks; a correction box never does.
    tone: Literal["definition", "note", "tip", "warning", "correction"] = "note"
    title: Short | None = None
    text: Text

    def _texts(self) -> list[str]:
        if self.tone == "correction" and self.book_errors:
            raise ValueError("a book correction box carries no book-error marks")
        return [*([self.title] if self.title else []), self.text]


class Table(_Marked):
    type: Literal["table"]
    caption: Short
    header: list[Annotated[str, Field(max_length=200)]] = Field(min_length=1, max_length=12)
    rows: list[list[Annotated[str, Field(max_length=500)]]] = Field(min_length=1, max_length=60)
    # TABLE-MERGE-01: columns where the book merges a cell down over several rows; there a blank cell continues the
    # filled cell above it.
    merged_columns: list[Annotated[int, Field(ge=0)]] | None = Field(default=None, max_length=12)
    # [row, column] cells of a merged column that begin a new cell although blank (the book's empty cell).
    merge_starts: list[tuple[Annotated[int, Field(ge=0)], Annotated[int, Field(ge=0)]]] | None = Field(
        default=None, max_length=60
    )

    def _texts(self) -> list[str]:
        if self.merged_columns and max(self.merged_columns) >= len(self.header):
            raise ValueError("merged_columns names a column the table doesn't have")
        for r, c in self.merge_starts or []:
            if c not in (self.merged_columns or []) or r >= len(self.rows):
                raise ValueError("merge_starts names a cell outside the table's merged columns")
        return [self.caption, *self.header, *(c for r in self.rows for c in r)]


class Equation(_Marked):
    type: Literal["equation"]
    latex: Annotated[str, Field(min_length=1, max_length=2000)]
    display: bool = True
    text_alt: Annotated[str, Field(min_length=1, max_length=1000)]  # spoken/plain equivalent, always required
    fallback: Fallback | None = None

    def _texts(self) -> list[str]:
        # A mark in the LaTeX is typeset in red on the web; one in the text equivalent is marked where that is shown.
        return [self.text_alt, self.latex]


class CheckpointOption(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Annotated[str, Field(pattern=r"^[a-z0-9]{1,8}$")]
    text: Short


class AnswerFigure(BaseModel):
    """A drawn answer shown with a checkpoint's explanation, only once the learner reveals it (ANSWER-FIGURE-01): a
    self-check that asks the student to draw a graph, cycle or structure answers with the drawing, not words alone."""

    model_config = ConfigDict(extra="forbid")
    asset_version_id: AssetRef
    alt: Annotated[str, Field(min_length=3, max_length=500)]
    caption: Short | None = None
    long_description: Text | None = None


class Checkpoint(_Block):
    """A formative check at a lesson point (P07.S1.T3; CHECKPOINTS-01). `question`: 2 to 6 options, one key, and the
    explanation shown after answering. `self_check`: a prompt and what a good answer contains; no key. The key travels
    with the lesson: checkpoints are self-checks, never stored, scored or counted as learning evidence, and never reuse
    bank questions (whose keys stay isolated)."""

    type: Literal["checkpoint"]
    mode: Literal["question", "self_check"] = "question"
    prompt: Text
    options: list[CheckpointOption] = Field(default_factory=list, max_length=6)
    answer_id: str | None = None
    explanation: Text
    answer_figure: AnswerFigure | None = None

    @model_validator(mode="after")
    def _shape(self) -> Checkpoint:
        ids = [o.id for o in self.options]
        if self.mode == "question":
            if len(ids) < 2:
                raise ValueError("a question checkpoint needs at least two options")
            if len(set(ids)) != len(ids):
                raise ValueError("option ids must be unique")
            if self.answer_id not in ids:
                raise ValueError("answer_id must be one of the options")
        elif ids or self.answer_id is not None:
            raise ValueError("a self-check has no options or key")
        return self


class Example(_Marked):
    """A worked example (P07.S1.T1): the problem, numbered steps and the answer, all plain text."""

    type: Literal["example"]
    title: Short
    problem: Text
    steps: list[Annotated[str, Field(min_length=1, max_length=2000)]] = Field(min_length=1, max_length=20)
    answer: Text | None = None

    def _texts(self) -> list[str]:
        return [self.title, self.problem, *self.steps, *([self.answer] if self.answer else [])]


class Diagram(_Block):
    """An archived image (labelled diagram, graph, photo). Alt text and a caption are required; a long description
    carries what a complex diagram shows for learners who can't see it."""

    type: Literal["diagram"]
    asset_version_id: AssetRef
    alt: Annotated[str, Field(min_length=3, max_length=500)]
    caption: Short
    long_description: Text | None = None


class Handout(_Block):
    """A downloadable archived PDF (worksheet, summary sheet)."""

    type: Literal["handout"]
    asset_version_id: AssetRef
    title: Short
    description: Short | None = None


class Scene(_Block):
    """A named original scene the app knows how to draw. Unknown names stay readable through alt text."""

    type: Literal["scene"]
    scene: Literal["bacterial_shapes"]
    alt: Annotated[str, Field(min_length=3, max_length=500)]
    caption: Short
    long_description: Text | None = None


class Model3D(_Block):
    """An original three-dimensional model of a structure in the lesson (MODEL3D-01). `poster` is a rendered still;
    `frames` are evenly spaced stills of one full turn, so a phone can be dragged round the model without a 3D engine;
    `model` names the scene the web viewer can draw live. The text alternative carries the teaching."""

    type: Literal["model3d"]
    model: Annotated[str, Field(pattern=r"^[a-z0-9_]{2,40}$")]
    poster_asset_version_id: AssetRef
    frames: list[AssetRef] = Field(default_factory=list, max_length=48)
    alt: Annotated[str, Field(min_length=3, max_length=500)]
    caption: Short
    long_description: Text | None = None
    labels: list[Short] = Field(default_factory=list, max_length=20)  # the parts named on the render, in order
    fallback: Fallback | None = None  # the poster as a still, for renderer 1 clients (§5.4 rule 4)


AnyBlock = (
    Heading
    | Paragraph
    | ListBlock
    | Callout
    | Table
    | Equation
    | Checkpoint
    | Example
    | Diagram
    | Handout
    | Scene
    | Model3D
)
Block = Annotated[AnyBlock, Field(discriminator="type")]


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")
    blocks: list[Block] = Field(default_factory=list, max_length=400)


_body = TypeAdapter(Body)


@dataclass
class Validation:
    errors: list[str]
    warnings: list[str]
    block_types: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def parse(body: object) -> tuple[Body | None, list[str]]:
    try:
        return _body.validate_python(body), []
    except ValidationError as e:
        return None, [f"blocks{_loc(err['loc'])}: {err['msg']}" for err in e.errors()]


def _loc(loc: tuple[int | str, ...]) -> str:
    parts = [p for p in loc if p != "blocks"]
    return "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in parts)


def check_renderers(block_list: list[AnyBlock], *, for_publication: bool, where: str) -> tuple[list[str], list[str]]:
    """§5.4 rule 4 for any list of blocks (a lesson body, a question stem, an option…). Returns (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []
    for i, block in enumerate(block_list):
        spec = REGISTRY[block.type]
        floor = supported_renderer()
        needs = [p for p in PLATFORMS if spec.min_renderer[p] > floor[p]]
        if not needs:
            continue
        fb = getattr(block, "fallback", None)
        usable = fb is not None and fb.reviewed and fb.image_asset_id and fb.alt
        if usable:
            continue
        msg = (
            f"{where}[{i}] ({block.type}): supported {', '.join(needs)} clients can't render this block yet; "
            "attach a reviewed fallback (static rendering, alt text and text equivalent)."
        )
        (errors if for_publication and spec.fallback_required_below else warnings).append(msg)
    return errors, warnings


def validate_body(body: object, *, for_publication: bool) -> Validation:
    parsed, errors = parse(body)
    if parsed is None:
        return Validation(errors, [], [])
    types: list[str] = sorted({b.type for b in parsed.blocks})
    if not parsed.blocks:
        errors.append("Add at least one block.")
    r_err, warnings = check_renderers(parsed.blocks, for_publication=for_publication, where="blocks")
    return Validation(errors + r_err, warnings, types)


def text_of(block_list: list[AnyBlock]) -> str:
    """Canonical plain text of blocks, for duplicate detection (never for display)."""
    parts: list[str] = []
    for b in block_list:
        for attr in (
            "text",
            "title",
            "caption",
            "latex",
            "text_alt",
            "prompt",
            "explanation",
            "problem",
            "answer",
            "alt",
        ):
            v = getattr(b, attr, None)
            if isinstance(v, str):
                parts.append(v)
        for attr in ("items", "header", "steps"):
            v = getattr(b, attr, None)
            if isinstance(v, list):
                parts.extend(str(x) for x in v)
        if isinstance(b, Checkpoint):
            parts.extend(o.text for o in b.options)
        rows = getattr(b, "rows", None)
        if isinstance(rows, list):
            parts.extend(str(c) for r in rows for c in r)
    return " ".join(" ".join(parts).lower().split())


def registry_document() -> dict[str, object]:
    return {
        "content_schema_version": CONTENT_SCHEMA_VERSION,
        "supported_renderer": supported_renderer(),
        "blocks": [
            {
                "type": s.type,
                "version": s.version,
                "min_renderer": s.min_renderer,
                "fallback_required": s.fallback_required_below,
                "description": s.description,
            }
            for s in REGISTRY.values()
        ],
    }


def needs_fallback(block_type: str) -> bool:
    """Whether the oldest supported client on any platform can't render this block type natively."""
    spec = REGISTRY.get(block_type)
    floor = supported_renderer()
    return spec is not None and any(spec.min_renderer[p] > floor[p] for p in PLATFORMS)


def oldest_client(block_list: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """What the oldest supported client shows: blocks it can't render become their reviewed fallback (§5.4 rule 4).
    Shared by the form preview (FORM-PREVIEW-01) and the studio surface report (SURFACES-01)."""
    out, replaced = [], 0
    for b in block_list:
        if needs_fallback(str(b.get("type"))):
            replaced += 1
            fb = b.get("fallback") or {}
            out.append({"type": "fallback", "text": fb.get("text", ""), "image_asset_id": fb.get("image_asset_id")})
        else:
            out.append(b)
    return out, replaced
