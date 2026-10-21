"""Qualification records and requalification triggers (roadmap Sections 6.4 and 6.5, P20.S4.T4; QUALIFICATION-01).

    python -m portal_api.qualification check                     # validates every record (exit 1 on a problem)
    python -m portal_api.qualification snapshot                  # the live content set's shape, from the database
    python -m portal_api.qualification impact [--head REV] [--content SNAPSHOT.json]

A capacity, security or device claim is bound to the release manifest that was measured. A QualificationRecord
(`docs/project/qualification/records/*.json`) stores the scenario, that manifest (the output of
`python -m portal_api.release manifest` for the measured build), the environment, data volume, results and
limitations, and optionally a content snapshot taken with the measurement.

`impact` is the release-checklist step. For each record it compares the measured build with the candidate: the files
changed since the measured commit, the manifest fields and, when both snapshots exist, the live content set. Each change
is matched against the Section 6.4 trigger table below. A material change lists the records it invalidates and the
retests they need before the claim is reused. Anything else needs only the standard release checks, as the table's last
row says for caption, text, copy and non-exam UI corrections.

The snapshot holds no academic text: item ids, kinds, versions, block types and byte sizes only.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

API_DIR = Path(__file__).resolve().parents[2]
REPO = API_DIR.parents[1]
RECORDS = REPO / "docs" / "project" / "qualification" / "records"

# What each retest is (Section 6.4's right-hand column). A record names the one scenario it measured.
SCENARIOS: dict[str, str] = {
    "persistence_failure": "Persistence failure suite (P10.S4)",
    "baseline_load": "Baseline load scenario (P20.S2)",
    "burst_load": "Burst load scenario (P20.S2.T2)",
    "ac45": "Answer-save and submit acceptance under delay, reordering and duplicate tabs (AC45)",
    "device_budgets": "Student-device end-to-end budgets (Section 6.2b, P20.S3.T3)",
    "rendering_spike": "Scientific content rendering spike (P01.S4.T2)",
    "content_compatibility": "Content compatibility across supported clients (P19.S3.T4)",
    "device_matrix": "Device matrix (P19.S2)",
    "startup_interruption": "Startup and interruption tests",
    "store_track": "Store-track requalification",
    "connection_budget": "Connection budget check (P17.S2.T4)",
    "catalogue_search": "Query-plan review and catalogue/search scenarios",
    "security_retest": "Targeted security retest (P18.S4)",
    "written_academic": "Affected written academic qualification",
    "written_capture": "Written reference-device capture",
    "written_workload_cost": "Written workload and cost evidence",
    "written_canary": "Written canary baseline compatibility",
    "written_acceptance": "Affected written and composite acceptance (WA)",
    "written_races": "Human-protection and ledger races",
    "composite_timing": "Composite timing and mixed-load checks",
}


@dataclass(frozen=True)
class Trigger:
    id: str
    change: str  # the Section 6.4 wording
    retests: tuple[str, ...]


TRIGGERS: dict[str, Trigger] = {
    t.id: t
    for t in (
        Trigger(
            "attempt_schema",
            "Schema or index change on attempt, answer, receipt, entitlement or trial tables",
            ("persistence_failure", "burst_load"),
        ),
        Trigger(
            "attempt_endpoints",
            "Change to answer-save, submit, attempt-start or entitlement endpoints",
            ("baseline_load", "burst_load", "ac45"),
        ),
        Trigger(
            "exam_payload",
            "Exam payload size or first-question asset budget change > 20 %",
            ("device_budgets",),
        ),
        Trigger(
            "renderer",
            "New content schema version, block type or renderer dependency",
            ("rendering_spike", "content_compatibility", "device_matrix"),
        ),
        Trigger(
            "native_runtime",
            "Native dependency major change, Expo SDK/React Native upgrade, or runtime version change",
            ("device_matrix", "startup_interruption", "store_track"),
        ),
        Trigger(
            "infrastructure",
            "Infrastructure limit change (instance class, pool sizes, pooler mode, autoscaling maximum, provider plan)",
            ("connection_budget", "baseline_load", "burst_load"),
        ),
        Trigger(
            "content_growth",
            "Content bank growth beyond 2x the tested volume or a new launch course",
            ("catalogue_search",),
        ),
        Trigger(
            "security",
            "Security-relevant change (auth, authorisation, upload, export, webhook paths)",
            ("security_retest",),
        ),
        Trigger(
            "written_pipeline",
            "Written rubric/model/prompt/OCR/preprocessing/capture/notation or routing change",
            ("written_academic", "written_capture", "written_workload_cost", "written_canary"),
        ),
        Trigger(
            "written_state",
            "Written/composite state, allowance or result propagation change",
            ("written_acceptance", "written_races", "composite_timing"),
        ),
    )
}
NON_MATERIAL = "Caption, text, copy or non-exam UI corrections within tested ranges: none beyond standard checks"

_API = "apps/api/src/portal_api/"
# Source files whose change is a material trigger by itself. Tests, documentation and other code are not.
PATH_RULES: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (trigger, re.compile(pattern))
    for trigger, pattern in (
        ("attempt_endpoints", rf"^{_API}modules/assessment/(attempts|sessions|exam_room|mocks|router)\.py$"),
        ("attempt_endpoints", rf"^{_API}modules/access/(service|router|trial_devices)\.py$"),
        ("attempt_endpoints", rf"^{_API}modules/written/router\.py$"),
        ("renderer", r"^apps/(web|mobile)/src/components/lesson-blocks\.tsx$"),
        ("infrastructure", rf"^infra/|(^|/)Dockerfile[^/]*$|^{_API}(budget|db)\.py$"),
        (
            "security",
            rf"^{_API}(modules/identity/|modules/exports/|object_store\.py$|modules/written/storage\.py$"
            rf"|modules/system/(guard|scanning)\.py$)"
            r"|^apps/web/src/(proxy|middleware)\.ts$|^apps/web/src/lib/session\.ts$"
            r"|^apps/(api/src|web/src|mobile/src)/.*(upload|webhook)",
        ),
        ("written_pipeline", rf"^{_API}modules/written/(automatic|evidence|quality|mapping|academic|calibration)\.py$"),
        (
            "written_state",
            rf"^{_API}modules/written/(lifecycle|service|linked|regrade_jobs|rescans|review|adjudication)\.py$",
        ),
    )
)
MIGRATIONS = re.compile(r"^apps/api/migrations/versions/[^/]+\.py$")
BLOCKS = f"{_API}modules/content/blocks.py"
BLOCK_TYPE = re.compile(r'^\s+type: Literal\["(\w+)"\]', re.M)
PROTECTED_TABLE = re.compile(r"""["'](\w*(?:attempt|answer|receipt|entitlement|trial)\w*)["']""")
EXAM_KINDS = ("mcq", "written", "passage")  # what a learner's device downloads to sit a test (rubrics stay server-side)
PAYLOAD_CHANGE = 0.20


# ------------------------------------------------------------------ records
class QualificationRecord(BaseModel):
    """One measured scenario (Section 6.5)."""

    id: str = Field(pattern=r"^QR-\d{4}-\d{2}-\d{2}-[a-z0-9-]+$")
    scenario: str
    claim: str = Field(min_length=10, description="What this evidence supports, in one sentence")
    measured_at: date
    manifest: dict[str, Any] = Field(description="`python -m portal_api.release manifest` for the measured build")
    environment: str = Field(min_length=3)
    data_volume: str = Field(min_length=3)
    results: dict[str, Any]
    limitations: list[str]
    evidence: list[str] = Field(default_factory=list, description="Reports, CI runs or files with the raw results")
    content_snapshot: str | None = Field(
        default=None, description="Snapshot file next to this record, if one was taken"
    )

    @field_validator("scenario")
    @classmethod
    def _known_scenario(cls, v: str) -> str:
        if v not in SCENARIOS:
            raise ValueError(f"unknown scenario {v!r}; one of {sorted(SCENARIOS)}")
        return v

    @field_validator("manifest")
    @classmethod
    def _measured_build(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not re.fullmatch(r"[0-9a-f]{40}", str(v.get("git_commit") or "")):
            raise ValueError("the measured manifest needs the full 40-character git_commit")
        if not v.get("migration_head"):
            raise ValueError("the measured manifest needs its migration_head")
        return v


def load_records(directory: Path = RECORDS) -> tuple[list[QualificationRecord], list[str]]:
    records, problems = [], []
    paths = (
        sorted(p for p in directory.glob("*.json") if not p.name.endswith(".snapshot.json"))
        if directory.exists()
        else []
    )
    for path in paths:
        try:
            record = QualificationRecord.model_validate_json(path.read_text(encoding="utf-8"))
        except ValidationError as e:
            problems.append(f"{path.name}: {e.errors()[0]['loc']} {e.errors()[0]['msg']}")
            continue
        if path.stem != record.id:
            problems.append(f"{path.name}: the file name must be the record id ({record.id}.json)")
        if record.content_snapshot and not (directory / record.content_snapshot).exists():
            problems.append(f"{path.name}: content snapshot {record.content_snapshot} is missing")
        records.append(record)
    return records, problems


# ------------------------------------------------------------------ changes
@dataclass(frozen=True)
class Change:
    trigger: str
    detail: str


def _majors(package_json: str | None) -> dict[str, int]:
    if not package_json:
        return {}
    data = json.loads(package_json)
    out = {}
    for name, spec in {**data.get("dependencies", {}), **data.get("devDependencies", {})}.items():
        m = re.search(r"(\d+)\.", str(spec))
        if m:
            out[name] = int(m.group(1))
    return out


def _runtime_version(config: str | None) -> str | None:
    m = re.search(r"runtimeVersion:\s*([^,\n]+)", config or "")
    return m.group(1).strip() if m else None


def _upgrade_part(source: str) -> str:
    return source.split("def upgrade", 1)[1].split("def downgrade", 1)[0] if "def upgrade" in source else source


def changes_from_paths(paths: Iterable[str], base: str, read_at: Callable[[str, str], str | None]) -> list[Change]:
    """`read_at(rev, path)` returns a file's text at a revision ("" for the candidate), or None if absent there."""
    changes: list[Change] = []
    for path in sorted(set(paths)):
        changes += [Change(t, path) for t in dict.fromkeys(t for t, pattern in PATH_RULES if pattern.search(path))]
        if MIGRATIONS.match(path):
            tables = sorted(set(PROTECTED_TABLE.findall(_upgrade_part(read_at("", path) or read_at(base, path) or ""))))
            if tables:
                changes.append(Change("attempt_schema", f"{path} ({', '.join(tables)})"))
        elif path in ("apps/mobile/package.json", "apps/web/package.json"):
            before, after = _majors(read_at(base, path)), _majors(read_at("", path))
            moved = sorted(n for n in after.keys() & before.keys() if after[n] != before[n])
            if moved:
                trigger = "native_runtime" if path.startswith("apps/mobile") else "renderer"
                changes.append(Change(trigger, f"{path}: major version of {', '.join(moved)}"))
        elif path == BLOCKS:
            added = sorted(
                set(BLOCK_TYPE.findall(read_at("", path) or "")) - set(BLOCK_TYPE.findall(read_at(base, path) or ""))
            )
            if added:
                changes.append(Change("renderer", f"new block types in the registry: {', '.join(added)}"))
        elif path == "apps/mobile/app.config.ts":
            if _runtime_version(read_at(base, path)) != _runtime_version(read_at("", path)):
                changes.append(Change("native_runtime", f"{path}: runtime version"))
    return changes


def changes_from_manifests(measured: dict[str, Any], current: dict[str, Any]) -> list[Change]:
    changes = []
    for key in ("content_schema_version", "supported_renderer"):
        if key in measured and measured.get(key) != current.get(key):
            changes.append(Change("renderer", f"manifest {key}: {measured.get(key)} -> {current.get(key)}"))
    if "connection_budget" in measured and measured.get("connection_budget") != current.get("connection_budget"):
        changes.append(Change("infrastructure", "manifest connection_budget changed"))
    return changes


def _courses(snapshot: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for item in snapshot["items"]:
        out.setdefault(f"{item['grade']}-{item['subject']}", []).append(item)
    return out


def _exam_sizes(items: list[dict[str, Any]]) -> tuple[float, int]:
    """Mean bytes per exam item (an exam payload of N questions scales with it) and the largest item's asset bytes."""
    exam = [i for i in items if i["kind"] in EXAM_KINDS]
    if not exam:
        return 0.0, 0
    mean = sum(i["body_bytes"] + i["asset_bytes"] for i in exam) / len(exam)
    return mean, max(i["asset_bytes"] for i in exam)


def _moved(before: float, after: float) -> bool:
    return before > 0 and abs(after - before) / before > PAYLOAD_CHANGE


def changes_from_content(measured: dict[str, Any], current: dict[str, Any]) -> list[Change]:
    changes = []
    old_items = {i["id"]: i for i in measured["items"]}
    new_items = {i["id"]: i for i in current["items"]}
    new_blocks = sorted(
        {b for i in current["items"] for b in i["block_types"]}
        - {b for i in measured["items"] for b in i["block_types"]}
    )
    if new_blocks:
        changes.append(Change("renderer", f"new block types live: {', '.join(new_blocks)}"))
    new_schemas = sorted({i["schema"] for i in current["items"]} - {i["schema"] for i in measured["items"]})
    if new_schemas:
        changes.append(Change("renderer", f"new content schema versions live: {new_schemas}"))
    before, after = _courses(measured), _courses(current)
    for course in sorted(after):
        if course not in before:
            changes.append(Change("content_growth", f"{course}: a new course is live"))
            continue
        if len(after[course]) > 2 * len(before[course]):
            changes.append(
                Change("content_growth", f"{course}: {len(before[course])} -> {len(after[course])} live items")
            )
        (mean0, first0), (mean1, first1) = _exam_sizes(before[course]), _exam_sizes(after[course])
        if _moved(mean0, mean1):
            changes.append(Change("exam_payload", f"{course}: mean exam item {mean0:.0f} -> {mean1:.0f} bytes"))
        if _moved(first0, first1):
            changes.append(Change("exam_payload", f"{course}: largest question asset {first0} -> {first1} bytes"))
    rubrics = sorted(
        i
        for i, item in new_items.items()
        if item["kind"] == "rubric" and old_items.get(i, {}).get("version") != item["version"]
    )
    if rubrics:
        changes.append(Change("written_pipeline", f"{len(rubrics)} rubric(s) published or changed"))
    return changes


# ------------------------------------------------------------------ impact
def impact(
    records: list[QualificationRecord],
    *,
    changed_paths: Callable[[str], list[str]],
    read_at: Callable[[str, str], str | None],
    current_manifest: dict[str, Any],
    current_content: dict[str, Any] | None,
    load_snapshot: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    """Which records the candidate invalidates, and why. `changed_paths(commit)` lists files changed since `commit`."""
    rows = []
    for r in records:
        base = r.manifest["git_commit"]
        changes = changes_from_paths(changed_paths(base), base, read_at)
        changes += changes_from_manifests(r.manifest, current_manifest)
        content_compared = bool(r.content_snapshot and current_content is not None)
        if r.content_snapshot and current_content is not None:
            changes += changes_from_content(load_snapshot(r.content_snapshot), current_content)
        fired = sorted({c.trigger for c in changes})
        because = [c for c in changes if r.scenario in TRIGGERS[c.trigger].retests]
        rows.append(
            {
                "id": r.id,
                "scenario": r.scenario,
                "measured_commit": base,
                "invalidated": bool(because),
                "retest": SCENARIOS[r.scenario] if because else None,
                "because": [{"trigger": TRIGGERS[c.trigger].change, "detail": c.detail} for c in because],
                "material_changes": fired,
                "content_compared": content_compared,
            }
        )
    report: dict[str, Any] = {
        "records": rows,
        "invalidated": [row["id"] for row in rows if row["invalidated"]],
        # None, not True, when there is nothing to reuse: no record means no claim is evidenced at all.
        "standard_checks_only": not any(row["invalidated"] for row in rows) if rows else None,
    }
    if not rows:
        report["note"] = "No qualification record exists: no capacity, security or device claim is evidenced yet."
    return report


# ------------------------------------------------------------------ snapshot (database)
def _asset_versions(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            if k.endswith("asset_version_id") and isinstance(v, str):
                found.append(v)
            else:
                found += _asset_versions(v)
    elif isinstance(value, list):
        for v in value:
            found += _asset_versions(v)
    return found


def content_snapshot(db: Any) -> dict[str, Any]:
    """The live content set's shape: per item its kind, course, published version, block types and byte sizes.

    Asset bytes are the archived masters' sizes, an upper bound on what a device downloads."""
    import uuid

    from sqlalchemy import select

    from portal_api.modules.content.assets import AssetVersion
    from portal_api.modules.content.models import Availability, ContentItem, ContentVersion

    rows = db.execute(
        select(ContentItem, ContentVersion)
        .join(ContentVersion, ContentVersion.id == ContentItem.published_version_id)
        .where(ContentItem.availability == Availability.live.value)
        .order_by(ContentItem.id)
    ).all()
    refs = {ref for _, v in rows for ref in _asset_versions(v.body)}
    ids = []
    for ref in refs:
        try:
            ids.append(uuid.UUID(ref))
        except ValueError:
            continue
    sizes = (
        {str(a.id): a.master_bytes for a in db.scalars(select(AssetVersion).where(AssetVersion.id.in_(ids)))}
        if ids
        else {}
    )
    return {
        "snapshot_version": 1,
        "taken_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "items": [
            {
                "id": str(item.id),
                "kind": item.kind,
                "grade": item.grade_number,
                "subject": item.subject_code,
                "version": version.number,
                "schema": version.content_schema_version,
                "block_types": sorted(version.block_types or []),
                "body_bytes": len(json.dumps(version.body, sort_keys=True, separators=(",", ":")).encode()),
                "asset_bytes": sum(sizes.get(ref, 0) for ref in set(_asset_versions(version.body))),
            }
            for item, version in rows
        ],
    }


# ------------------------------------------------------------------ git and CLI
def _git(*args: str) -> str:
    # fixed git subcommands with revisions and paths from this repository's records; git from PATH as in CI
    command = ["git", *args]
    return subprocess.run(command, cwd=REPO, capture_output=True, text=True, check=True).stdout  # noqa: S603


def _git_paths(head: str) -> Callable[[str], list[str]]:
    def changed(base: str) -> list[str]:
        try:
            return _git("diff", "--name-only", "--no-renames", base, head).split()
        except subprocess.CalledProcessError:
            raise SystemExit(
                f"commit {base} is not in this checkout; fetch the full history (git fetch --unshallow)"
            ) from None

    return changed


def _git_read(head: str) -> Callable[[str, str], str | None]:
    def read(rev: str, path: str) -> str | None:
        try:
            return _git("show", f"{rev or head}:{path}")
        except subprocess.CalledProcessError:
            return None

    return read


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    records, problems = load_records()
    if args[:1] == ["check"]:
        for p in problems:
            print(p)
        print(f"qualification records: {len(records)}, problems: {len(problems)}")
        return 1 if problems else 0
    if args[:1] == ["snapshot"]:
        from portal_api.db import get_sessionmaker

        with get_sessionmaker()() as db:
            print(json.dumps(content_snapshot(db), indent=1, sort_keys=True))
        return 0
    if args[:1] == ["impact"]:
        if problems:
            print("\n".join(problems))
            return 1
        head = args[args.index("--head") + 1] if "--head" in args else "HEAD"
        content = (
            json.loads(Path(args[args.index("--content") + 1]).read_text(encoding="utf-8"))
            if "--content" in args
            else None
        )
        from portal_api.release import manifest

        report = impact(
            records,
            changed_paths=_git_paths(head),
            read_at=_git_read(head),
            current_manifest=manifest(),
            current_content=content,
            load_snapshot=lambda name: json.loads((RECORDS / name).read_text(encoding="utf-8")),
        )
        print(json.dumps(report, indent=2))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
