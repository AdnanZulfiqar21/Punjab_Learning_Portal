"""P20.S4.T4 (QUALIFICATION-01): qualification evidence is bound to the measured release manifest, and the release
checklist lists exactly the records a change invalidates (Section 6.4 trigger table, AC51).

The records and snapshots here are labelled technical fixtures that exercise the tool. They are not qualification
evidence: no load, device or security scenario was run for them."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from portal_api import qualification as q
from tests import test_content_workflow
from tests.test_content_workflow import FIXTURE_BODY, Staff, _confirm_rights, _post, _refs, _save, _submitted

team = test_content_workflow.team  # the Class 11 Biology staff fixture

APPROVE = {"decision": "approve", "comment": "Checked against source pages"}
COMMIT = "a" * 40  # a fixture commit, not a real measured build
MANIFEST: dict[str, Any] = {
    "git_commit": COMMIT,
    "migration_head": "fixturehead01",
    "content_schema_version": 1,
    "supported_renderer": {"web": 1, "android": 1, "ios": 1},
    "connection_budget": {"fixture": 1},
}


def _record(scenario: str, slug: str, snapshot: str | None = "fixture-snapshot.json") -> q.QualificationRecord:
    return q.QualificationRecord(
        id=f"QR-2026-10-21-{slug}",
        scenario=scenario,
        claim="Fixture claim used only to exercise the release-checklist tool.",
        measured_at="2026-10-21",
        manifest=MANIFEST,
        environment="technical fixture (no environment was measured)",
        data_volume="technical fixture",
        results={"fixture": True},
        limitations=["Technical fixture; not qualification evidence."],
        content_snapshot=snapshot,
    )


RECORDS = [
    _record("device_budgets", "device-budgets"),
    _record("burst_load", "burst"),
    _record("security_retest", "security"),
    _record("rendering_spike", "rendering"),
    _record("catalogue_search", "catalogue"),
]


def _item(i: int, kind: str, body: int, assets: int = 0, version: int = 1) -> dict[str, Any]:
    return {
        "id": f"00000000-0000-0000-0000-{i:012d}",
        "kind": kind,
        "grade": 11,
        "subject": "biology",
        "version": version,
        "schema": 1,
        "block_types": ["paragraph"],
        "body_bytes": body,
        "asset_bytes": assets,
    }


MEASURED_CONTENT = {
    "snapshot_version": 1,
    "items": [
        _item(1, "lesson", 4000),
        _item(2, "mcq", 1000, assets=20_000),
        _item(3, "mcq", 1000),
        _item(4, "mcq", 1000),
    ],
}


def _impact(current_content: dict[str, Any], paths: list[str] | None = None) -> dict[str, Any]:
    return q.impact(
        RECORDS,
        changed_paths=lambda base: list(paths or []),
        read_at=lambda rev, path: None,
        current_manifest=copy.deepcopy(MANIFEST),
        current_content=current_content,
        load_snapshot=lambda name: MEASURED_CONTENT,
    )


def test_the_trigger_table_covers_every_scenario() -> None:
    retested = {s for t in q.TRIGGERS.values() for s in t.retests}
    assert retested <= set(q.SCENARIOS)
    assert retested == set(q.SCENARIOS)  # every scenario a record can name is retested by some trigger


def test_ac51_an_exam_payload_change_lists_exactly_the_invalidated_records() -> None:
    changed = copy.deepcopy(MEASURED_CONTENT)
    changed["items"][1] |= {"body_bytes": 2000, "asset_bytes": 30_000, "version": 2}  # a bigger question and figure
    report = _impact(changed)
    assert report["invalidated"] == ["QR-2026-10-21-device-budgets"]
    row = next(r for r in report["records"] if r["invalidated"])
    assert row["retest"] == q.SCENARIOS["device_budgets"] and row["content_compared"]
    assert {b["trigger"] for b in row["because"]} == {q.TRIGGERS["exam_payload"].change}
    assert any("largest question asset 20000 -> 30000" in b["detail"] for b in row["because"])
    assert not report["standard_checks_only"]


def test_ac51_a_caption_correction_lists_none() -> None:
    changed = copy.deepcopy(MEASURED_CONTENT)
    changed["items"][0] |= {"body_bytes": 4012, "version": 2}  # corrected caption text in a lesson
    changed["items"][2] |= {"body_bytes": 1006, "version": 2}  # and a corrected word in a question
    report = _impact(changed)
    assert report["invalidated"] == [] and report["standard_checks_only"]
    assert all(r["material_changes"] == [] for r in report["records"])


def test_other_content_changes_follow_the_table() -> None:
    grown = copy.deepcopy(MEASURED_CONTENT)
    grown["items"] += [_item(10 + i, "lesson", 4000) for i in range(5)]  # 4 -> 9 live items: beyond 2x
    grown["items"].append(_item(99, "lesson", 4000) | {"grade": 12, "subject": "physics"})  # a new course
    grown["items"][0]["block_types"] = ["paragraph", "chemical_equation"]  # a block type never measured
    report = _impact(grown)
    assert report["invalidated"] == ["QR-2026-10-21-rendering", "QR-2026-10-21-catalogue"]
    details = [b["detail"] for r in report["records"] for b in r["because"]]
    assert "12-physics: a new course is live" in details and "11-biology: 4 -> 9 live items" in details
    assert "new block types live: chemical_equation" in details

    rubric = copy.deepcopy(MEASURED_CONTENT)
    rubric["items"].append(_item(50, "rubric", 900))
    assert [c.trigger for c in q.changes_from_content(MEASURED_CONTENT, rubric)] == ["written_pipeline"]


def test_code_changes_map_to_the_section_6_4_rows() -> None:
    files: dict[tuple[str, str], str] = {
        ("", "apps/api/migrations/versions/20261101_a_answers.py"): (
            'def upgrade() -> None:\n    op.add_column("attempt_answer", sa.Column("x", sa.Integer()))\n\n'
            "def downgrade() -> None:\n    pass\n"
        ),
        ("", "apps/api/migrations/versions/20261101_b_help.py"): (
            'def upgrade() -> None:\n    op.add_column("help_article", sa.Column("x", sa.Integer()))\n\n'
            "def downgrade() -> None:\n    pass\n"
        ),
        (COMMIT, "apps/mobile/package.json"): json.dumps({"dependencies": {"expo": "~57.0.27", "zod": "^4.1.0"}}),
        ("", "apps/mobile/package.json"): json.dumps({"dependencies": {"expo": "~58.0.1", "zod": "^4.2.0"}}),
        (COMMIT, "apps/web/package.json"): json.dumps({"dependencies": {"next": "16.4.0"}}),
        ("", "apps/web/package.json"): json.dumps({"dependencies": {"next": "16.4.2"}}),
        (COMMIT, q.BLOCKS): '    type: Literal["paragraph"]\n',
        ("", q.BLOCKS): '    type: Literal["paragraph"]\n    type: Literal["chemical_equation"]\n',
    }

    def read_at(rev: str, path: str) -> str | None:
        return files.get((rev, path))

    def triggers(*paths: str) -> list[str]:
        return [c.trigger for c in q.changes_from_paths(paths, COMMIT, read_at)]

    assert triggers("apps/web/src/app/page.tsx", "docs/project/DECISIONS.md", "apps/api/tests/test_x.py") == []
    assert triggers("apps/web/package.json") == []  # a patch upgrade
    assert triggers("apps/api/migrations/versions/20261101_b_help.py") == []
    assert triggers("apps/api/migrations/versions/20261101_a_answers.py") == ["attempt_schema"]
    assert triggers("apps/mobile/package.json") == ["native_runtime"]
    assert triggers(q.BLOCKS) == ["renderer"]
    assert triggers("apps/api/src/portal_api/modules/assessment/attempts.py") == ["attempt_endpoints"]
    assert triggers("apps/api/src/portal_api/modules/identity/router.py") == ["security"]
    assert triggers("apps/web/src/app/studio/uploads/[id]/route.ts") == ["security"]
    assert triggers("apps/api/src/portal_api/modules/written/automatic.py") == ["written_pipeline"]
    assert triggers("apps/api/src/portal_api/modules/written/lifecycle.py") == ["written_state"]
    assert triggers("infra/docker-compose.yml") == ["infrastructure"]

    # A schema change on answers invalidates the burst record, and only it, among the fixtures.
    report = q.impact(
        RECORDS,
        changed_paths=lambda base: ["apps/api/migrations/versions/20261101_a_answers.py"],
        read_at=read_at,
        current_manifest=copy.deepcopy(MANIFEST),
        current_content=None,
        load_snapshot=lambda name: MEASURED_CONTENT,
    )
    assert report["invalidated"] == ["QR-2026-10-21-burst"]
    assert not any(r["content_compared"] for r in report["records"])  # no candidate snapshot was given


def test_manifest_changes_follow_the_table() -> None:
    current = copy.deepcopy(MANIFEST) | {"content_schema_version": 2, "connection_budget": {"fixture": 2}}
    assert [c.trigger for c in q.changes_from_manifests(MANIFEST, current)] == ["renderer", "infrastructure"]
    assert q.changes_from_manifests(MANIFEST, copy.deepcopy(MANIFEST)) == []


def test_records_need_a_measured_build(tmp_path: Path) -> None:
    good = _record("burst_load", "burst", snapshot=None).model_dump(mode="json")
    for broken in (
        good | {"scenario": "made_up"},
        good | {"manifest": MANIFEST | {"git_commit": "abc123"}},
        good | {"manifest": {k: v for k, v in MANIFEST.items() if k != "migration_head"}},
        good | {"id": "burst"},
    ):
        with pytest.raises(ValidationError):
            q.QualificationRecord.model_validate(broken)
    (tmp_path / "QR-2026-10-21-other.json").write_text(json.dumps(good), encoding="utf-8")
    (tmp_path / "QR-2026-10-21-snap.json").write_text(
        json.dumps(good | {"id": "QR-2026-10-21-snap", "content_snapshot": "missing.json"}), encoding="utf-8"
    )
    (tmp_path / "QR-2026-10-21-other.snapshot.json").write_text(json.dumps(MEASURED_CONTENT), encoding="utf-8")
    records, problems = q.load_records(tmp_path)
    assert len(records) == 2 and len(problems) == 2  # the snapshot file is not read as a record
    assert any("file name must be the record id" in p for p in problems)
    assert any("missing.json is missing" in p for p in problems)


def test_the_repository_records_are_valid_and_linked_from_the_manifest(capsys: pytest.CaptureFixture[str]) -> None:
    from portal_api import release

    assert q.main(["check"]) == 0
    capsys.readouterr()
    records, _ = q.load_records()
    linked = release.manifest()["qualification_records"]
    assert [r["id"] for r in linked] == [r.id for r in records]
    assert q.main(["impact"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert len(report["records"]) == len(records)
    if not records:  # nothing measured yet: the checklist must not read as "standard checks only"
        assert report["standard_checks_only"] is None and "no capacity, security or device claim" in report["note"]


def test_the_snapshot_holds_shapes_not_text(client: TestClient, db: Session, team: dict[str, Staff]) -> None:
    """A real published lesson, then a corrected sentence: the snapshot changes, and no Section 6.4 row fires."""
    item, chapter, doc = _submitted(client, db, team)
    _confirm_rights(client, db, doc)
    assert _post(client, team["reviewer"], item["id"], "review", APPROVE).status_code == 200
    assert _post(client, team["publisher"], item["id"], "publish").status_code == 200
    before = q.content_snapshot(db)
    row = next(i for i in before["items"] if i["id"] == item["id"])
    assert row["kind"] == "lesson" and row["version"] == 1 and row["body_bytes"] > 0
    assert row["block_types"] == ["heading", "paragraph"] and row["asset_bytes"] == 0
    assert "Technical fixture paragraph" not in json.dumps(before) and item["title"] not in json.dumps(before)

    assert _post(client, team["author"], item["id"], "revise", {"reason": "Fixture text correction"}).status_code == 200
    rev = client.get(f"/v1/studio/items/{item['id']}", headers=team["author"].headers).json()
    corrected = copy.deepcopy(FIXTURE_BODY)
    corrected["blocks"][1]["text"] = "Technical fixture paragraph used only to exercise the workflow (corrected)."
    assert _save(client, team["author"], rev, body=corrected, refs=_refs(chapter, doc)).status_code == 200
    assert _post(client, team["author"], item["id"], "submit").status_code == 200
    assert _post(client, team["reviewer"], item["id"], "review", APPROVE).status_code == 200
    assert _post(client, team["publisher"], item["id"], "publish").status_code == 200
    db.expire_all()
    after = q.content_snapshot(db)
    assert next(i for i in after["items"] if i["id"] == item["id"])["version"] == 2
    assert q.changes_from_content(before, after) == []
