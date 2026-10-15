"""W01.S2.T2 (MARKING-RULES-01): a marking guide states its own rules for significant figures and for several or
contradictory final answers; a marker sees the guide's rules, and the §20.6.3 proposed default (labelled as one) where
the guide states none; and a correction that changes any such rule never carries old marks forward. Technical fixture
rubrics only."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from portal_api.modules.content import written as wq
from portal_api.modules.written import adjudication
from tests.test_rescans import _case, _sealed, _staff
from tests.test_written_records import _rubric


def test_a_guide_states_each_rule_and_unstated_ones_get_labelled_defaults() -> None:
    body = {
        **_rubric(str(uuid.uuid4())),
        "units_rule": "Fixture: units required on the final answer",
        "significant_figures_rule": "Fixture: three significant figures, one deduction per answer",
        "final_answers_rule": "Fixture: two different final answers earn no final-answer credit",
    }
    r, errors = wq.parse_rubric(body)  # authoring validation is strict, so the new fields are known
    assert r is not None and not errors
    rules = wq.marking_rules(r)
    assert [x["key"] for x in rules] == [
        "units_rule",
        "significant_figures_rule",
        "final_answers_rule",
        "crossed_out_rule",
    ]
    assert [x["proposed_default"] for x in rules] == [False, False, False, True]
    assert rules[1]["label"] == "Significant figures" and rules[1]["text"].startswith("Fixture: three")
    assert "pending and escalate" in str(rules[3]["text"])

    bare, _ = wq.parse_rubric(_rubric(str(uuid.uuid4())))
    assert bare is not None
    defaults = {str(x["key"]): x for x in wq.marking_rules(bare)}
    assert set(defaults) == {"final_answers_rule", "crossed_out_rule"}  # units and figures have no universal default
    assert all(x["proposed_default"] for x in defaults.values())
    assert "Don't choose one" in str(defaults["final_answers_rule"]["text"])


def test_changing_a_figures_or_final_answer_rule_never_carries_marks_forward() -> None:
    old = _rubric(str(uuid.uuid4()))
    for field in ("significant_figures_rule", "final_answers_rule"):
        out = adjudication.compatibility(old, {**old, field: "Fixture: a stricter rule"})
        assert out["rubric_fields_changed"] == [field] and out["carry_forward"] is False
    assert adjudication.compatibility(old, dict(old))["carry_forward"] is True


def test_the_marker_sees_the_guide_s_rules_or_the_labelled_defaults(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    _, attempt = _sealed(client, published_written["chapter"], seed=991)
    t = _staff(client)
    case = _case(client, t, attempt["id"], "initial")
    detail = client.get(f"/v1/studio/written/cases/{case['id']}", headers=t.headers).json()
    rules = detail["questions"][0]["marking_rules"]
    assert {r["key"] for r in rules} == {"final_answers_rule", "crossed_out_rule"}  # the fixture guide states none
    assert all(r["proposed_default"] and r["label"] and r["text"] for r in rules)
