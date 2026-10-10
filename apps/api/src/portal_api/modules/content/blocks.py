"""Content block schema and renderer capability registry (roadmap §5.4).

Every content version stores `content_schema_version` and the block types it uses. Each block type declares the minimum
renderer version per platform and whether a reviewed fallback is mandatory. Publication is rejected when a block needs
a renderer newer than the oldest supported client and no reviewed fallback is attached (§5.4 rule 4).

Blocks hold the author's own explanatory text. They never embed textbook page images or long verbatim passages; source
material is referenced by page (`source_refs`), not copied (IMPL-01).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, model_validator

CONTENT_SCHEMA_VERSION = 1
PLATFORMS = ("web", "android", "ios")

# Oldest renderer version each platform's supported clients understand. Raised only through the client update policy
# (P13.S1.T4); a full supported-client registry with per-build manifests arrives with P13.
SUPPORTED_RENDERER: dict[str, int] = {"web": 1, "android": 1, "ios": 1}


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
        # Equations need a typeset renderer. No client ships one yet (P01.S4.T2 rendering spike), so every equation
        # needs a reviewed static rendering plus its text equivalent before it can be published.
        BlockSpec("equation", 1, {"web": 2, "android": 2, "ios": 2}, True, "LaTeX equation with text equivalent."),
        # P07.S1.T3: formative only. Renderer v1 includes it on every platform because no native build had shipped when
        # it was added (B07); after a store release, a new block type must raise the renderer version instead.
        BlockSpec("checkpoint", 1, {"web": 1, "android": 1, "ios": 1}, True, "Formative question or self-check."),
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


class Heading(_Block):
    type: Literal["heading"]
    level: Literal[2, 3] = 2
    text: Short


class Paragraph(_Block):
    type: Literal["paragraph"]
    text: Text


class ListBlock(_Block):
    type: Literal["list"]
    ordered: bool = False
    items: list[Annotated[str, Field(min_length=1, max_length=1000)]] = Field(min_length=1, max_length=50)


class Callout(_Block):
    type: Literal["callout"]
    tone: Literal["definition", "note", "tip", "warning"] = "note"
    title: Short | None = None
    text: Text


class Table(_Block):
    type: Literal["table"]
    caption: Short
    header: list[Annotated[str, Field(max_length=200)]] = Field(min_length=1, max_length=12)
    rows: list[list[Annotated[str, Field(max_length=500)]]] = Field(min_length=1, max_length=60)


class Equation(_Block):
    type: Literal["equation"]
    latex: Annotated[str, Field(min_length=1, max_length=2000)]
    display: bool = True
    text_alt: Annotated[str, Field(min_length=1, max_length=1000)]  # spoken/plain equivalent, always required
    fallback: Fallback | None = None


class CheckpointOption(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Annotated[str, Field(pattern=r"^[a-z0-9]{1,8}$")]
    text: Short


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


AnyBlock = Heading | Paragraph | ListBlock | Callout | Table | Equation | Checkpoint
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
        needs = [p for p in PLATFORMS if spec.min_renderer[p] > SUPPORTED_RENDERER[p]]
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
        for attr in ("text", "title", "caption", "latex", "text_alt", "prompt", "explanation"):
            v = getattr(b, attr, None)
            if isinstance(v, str):
                parts.append(v)
        for attr in ("items", "header"):
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
        "supported_renderer": SUPPORTED_RENDERER,
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
