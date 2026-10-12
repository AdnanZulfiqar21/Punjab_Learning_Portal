"""P16.S2.T4 (ECONOMICS-01): the trial and paid cohort economics report.

Cost lines are measured quantities times rates finance entered with a source; nothing is estimated. Unmeasurable
quantities and unset rates are listed as missing, payment fees and contribution wait for payments (B06), and earlier
rates are kept. The "real" learners are fixture rows with a non-development issuer, inserted purely as test setup;
the rates are labelled fixtures, not real prices.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from portal_api.modules.analytics import economics
from portal_api.modules.audit.models import AuditEvent
from tests.test_business_overview import ISSUER, _real_learner
from tests.test_content_workflow import Staff
from tests.test_support_attachments import _ticket
from tests.test_trial_claims import _claim, _install

URL = "/v1/admin/analytics/economics"


def _report(client: TestClient, who: Staff) -> dict[str, Any]:
    r = client.get(URL, headers=who.headers)
    assert r.status_code == 200, r.text
    return dict(r.json())


def _pop(report: dict[str, Any], key: str) -> dict[str, Any]:
    return next(p for p in report["populations"] if p["key"] == key)


def _line(pop: dict[str, Any], key: str) -> dict[str, Any]:
    return next(line for line in pop["lines"] if line["key"] == key)


def _rate(client: TestClient, who: Staff, key: str, amount: str, currency: str = "USD") -> Any:
    return client.post(
        f"{URL}/rates",
        headers=who.headers,
        json={"key": key, "amount": amount, "currency": currency, "source_note": "Fixture: technical test rate"},
    )


def test_the_report_is_for_the_owner_and_finance_and_rates_for_finance(client: TestClient, db: Session) -> None:
    for who in (Staff(client, db, [], mfa=True), Staff(client, db, ["owner_admin"]), Staff(client, db, ["support"])):
        assert client.get(URL, headers=who.headers).status_code == 403
    assert client.get(URL, headers=Staff(client, db, ["owner_admin"], mfa=True).headers).status_code == 200
    for who in (Staff(client, db, [], mfa=True), Staff(client, db, ["finance"])):
        assert _rate(client, who, "email_per_1000", "0.5").status_code == 403
    assert {r.key for r in economics.RATES} == set(economics.RateKey.__args__)  # the contract lists every line


def test_costs_are_measured_quantities_times_entered_rates(client: TestClient, db: Session) -> None:
    finance = Staff(client, db, ["finance"], mfa=True)
    before = _report(client, finance)
    for pop in before["populations"]:  # nothing is priced yet: no costs, and every gap is named
        assert pop["known_cost"] == [] and pop["complete"] is False
        assert all(line["cost"] is None and not line["rate_set"] for line in pop["lines"])
        for gap in (
            "Video delivery: not measured (B05)",
            "Sign-in codes (OTP): not measured (B04)",
            "OCR and model use: not measured (B10)",
            "Payment fees and refunds: no payment provider (B06)",
            "Email: rate not set",
        ):
            assert gap in pop["missing"]
    assert before["contribution_per_paying_learner"] == {"value": None, "available": False, "blocker": "B06"}

    # One learner on a trial from the app, who asked for help once; one whose trial ended; one paying learner.
    app_learner = Staff(client, db, [])
    assert _claim(client, app_learner, _install()).json()["state"] == "granted"
    _ticket(client, app_learner)
    with get_sessionmaker()() as s:
        s.execute(text("update app_user set issuer = :i where id = :u"), {"i": ISSUER, "u": str(app_learner.id)})
        s.commit()
    _real_learner(trial_days_ago=40)  # ended 10 days ago, never paid
    payer = _real_learner()
    with get_sessionmaker()() as s:
        s.execute(
            text(
                "insert into entitlement (id, user_id, source, product_code, scope, starts_at, ends_at, status, "
                "written_units, reason) values (gen_random_uuid(), :u, 'paid', 'platform', '{}'::jsonb, "
                "now() - interval '1 day', now() + interval '29 days', 'active', 0, 'fixture purchase')"
            ),
            {"u": str(payer)},
        )
        s.commit()

    # Rates with their sources; a newer rate replaces the current one and the earlier one is kept.
    for key, amount in (
        ("hosting_per_learner_month", "2.5"),
        ("hosting_per_learner_month", "3"),
        ("support_per_ticket", "4"),
        ("attestation_per_1000", "1"),
        ("video_delivery_per_1000_minutes", "1"),
    ):
        assert _rate(client, finance, key, amount).status_code == 201
    assert _rate(client, finance, "email_per_1000", "0.5", currency="PKR").status_code == 422  # one currency
    assert _rate(client, finance, "email_per_1000", "-1").status_code == 422
    assert _rate(client, finance, "made_up_line", "1").status_code == 422
    with get_sessionmaker()() as s:
        kept = s.scalars(select(economics.CostRate.amount).where(economics.CostRate.key == "hosting_per_learner_month"))
        assert sorted(kept) == [Decimal("2.5"), Decimal("3")]
        assert s.scalar(select(AuditEvent.id).where(AuditEvent.action == "economics.rate_set")) is not None

    after = _report(client, finance)
    for key in ("paying", "trial", "completed_trial"):
        assert _pop(after, key)["learners"] - _pop(before, key)["learners"] == 1
    trial, old_trial = _pop(after, "trial"), _pop(before, "trial")
    for key in ("attestation_per_1000", "support_per_ticket"):
        assert Decimal(_line(trial, key)["quantity"]) - Decimal(_line(old_trial, key)["quantity"]) == 1
    rates = {r["key"]: r for r in after["rates"]}
    assert rates["hosting_per_learner_month"]["amount"] == "3.0000" and rates["email_per_1000"]["amount"] is None
    for pop in after["populations"]:
        total = Decimal(0)
        for line in pop["lines"]:
            rate = rates[line["key"]]
            if line["quantity"] is None or rate["amount"] is None:
                assert line["cost"] is None
                continue
            per = next(r.per for r in economics.RATES if r.key == line["key"])
            expected = (Decimal(line["quantity"]) * Decimal(rate["amount"]) / per).quantize(Decimal("0.01"))
            assert Decimal(line["cost"]) == expected and line["currency"] == "USD"
            total += expected
        known = pop["known_cost"]
        assert (known == [] and total == 0) or (known[0]["currency"] == "USD" and Decimal(known[0]["amount"]) == total)
        assert _line(pop, "video_delivery_per_1000_minutes")["cost"] is None  # a rate alone isn't a measurement
        assert "Video delivery: not measured (B05)" in pop["missing"] and pop["complete"] is False
    assert _pop(after, "trial")["known_cost_per_learner"][0]["amount"] == str(
        (Decimal(trial["known_cost"][0]["amount"]) / trial["learners"]).quantize(Decimal("0.01"))
    )
