"""P14.S8.T4 (TRIAL-QUALITY-01): trial decision quality and false blocks by cohort.

Claims, app claims, unknown verdicts, denials, appeals, overturned denials (the false-block proxy) and claims still
in review are counted from our own records for learners only; a week without denials has no overturned rate. Device
verdicts come from the fixture adapter; accounts are fixtures moved to a non-development issuer only as test setup.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from portal_api.modules.access import trial_devices
from tests.test_business_overview import ISSUER
from tests.test_content_workflow import Staff
from tests.test_trial_claims import _claim, _install

URL = "/v1/admin/analytics/trial-decisions"


def _week(report: dict[str, Any]) -> dict[str, Any]:
    with get_sessionmaker()() as db:
        start: date = db.execute(text("select date_trunc('week', timezone('Asia/Karachi', now()))::date")).scalar_one()
    empty = {k: 0 for k in ("claims", "app_claims", "unknown_verdicts", "denials", "appeals", "overturned_denials")}
    return next((c for c in report["cohorts"] if c["week_start"] == start.isoformat()), empty)


def test_trial_decision_quality_by_cohort(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    for who in (Staff(client, db, [], mfa=True), Staff(client, db, ["owner_admin"]), Staff(client, db, ["support"])):
        assert client.get(URL, headers=who.headers).status_code == 403
    finance, support = Staff(client, db, ["finance"], mfa=True), Staff(client, db, ["support"], mfa=True)
    before = _week(client.get(URL, headers=finance.headers).json())

    granted, appealed, denied, unknown = (Staff(client, db, []) for _ in range(4))
    assert _claim(client, granted, _install()).json()["state"] == "granted"
    install = _install()
    assert _claim(client, appealed, install, verdict="consumed").json()["state"] == "device_used"
    ticket = client.post(
        "/v1/support/tickets",
        headers=appealed.headers,
        json={"category": "access", "subject": "Fixture: trial refused", "body": "Fixture: second-hand phone."},
    )
    assert ticket.status_code == 201
    exception = {"email": appealed.email, "surface": "android", "days": 7, "reason": "Fixture: receipt seen"}
    assert client.post("/v1/staff/trial/exceptions", headers=support.headers, json=exception).status_code == 201
    assert _claim(client, appealed, install, verdict="consumed").json()["state"] == "granted"
    assert _claim(client, denied, _install(), verdict="consumed").json()["state"] == "device_used"

    def down(self: Any, proof: dict[str, Any]) -> Any:
        raise ConnectionError("attestation provider timed out")

    monkeypatch.setattr(trial_devices.FixtureProvider, "evaluate", down)
    assert _claim(client, unknown, _install()).json()["state"] == "verification_pending"
    monkeypatch.undo()
    with get_sessionmaker()() as s:  # learners, not test accounts, for the report
        for who in (granted, appealed, denied, unknown):
            s.execute(text("update app_user set issuer = :i where id = :u"), {"i": ISSUER, "u": str(who.id)})
        s.commit()

    report = client.get(URL, headers=finance.headers).json()
    after = _week(report)
    keys = ("claims", "app_claims", "unknown_verdicts", "denials", "appeals", "overturned_denials")
    assert {k: after[k] - before[k] for k in keys} == {
        "claims": 5,  # the appealed learner claimed twice: refused, then granted after the exception
        "app_claims": 5,
        "unknown_verdicts": 1,
        "denials": 2,
        "appeals": 1,
        "overturned_denials": 1,
    }
    rate = (Decimal(100 * after["overturned_denials"]) / after["denials"]).quantize(Decimal("0.1"))
    assert Decimal(after["overturned_rate"]) == rate and after["meets_target"] is (rate < 2)
    assert Decimal(after["denial_rate"]) == (Decimal(100 * after["denials"]) / after["claims"]).quantize(Decimal("0.1"))
    assert {c["line"] for c in after["trial_cost"]} <= {"Device checks", "Access help requests after a denial"}
    assert report["appeals_owner"] is None and "P14.S8.T1" in report["appeals_owner_note"]
    assert "B07" in report["evidence_note"] and report["target_overturned_percent"] in ("2", 2)
