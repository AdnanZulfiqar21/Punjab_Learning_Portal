"""P14.S1.T1 (PRODUCTS-01): sellable products. Finance staff (MFA, audited) define a product's kind, scope, duration
and written allowance; activation freezes the definition; prices are append-only versions in integer minor units per
channel, so history is never rewritten; the public listing shows only what is on sale, without staff fields. Scope
follows the live catalogue and exam profiles. Every product, code and amount here is a labelled technical fixture,
not a real offer or price."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.test_content_workflow import Staff


def _code(tag: str) -> str:
    return f"fx-{tag}-{uuid.uuid4().hex[:8]}"


def _product(code: str, kind: str = "subject_package", **extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "code": code,
        "name": "Fixture package (not a real offer)",
        "kind": kind,
        "scope": {"grades": [11], "subjects": ["biology"]},
        "duration_days": 180,
        "written_units": 4,
        "description": "Technical fixture.",
    }
    body.update(extra)
    return body


def _price(amount: int | None = 250_000, **extra: Any) -> dict[str, Any]:
    return {"currency": "PKR", "amount_minor": amount, "reason": "Fixture price for a test", **extra}


def test_finance_defines_prices_and_retires_a_product_without_rewriting_history(
    client: TestClient, db: Session
) -> None:
    finance = Staff(client, db, ["finance"], None, mfa=True)
    no_mfa = Staff(client, db, ["finance"], None, mfa=False)
    author = Staff(client, db, ["content_author"], {"grades": [11], "subjects": ["biology"]})
    code = _code("bio")
    assert client.post("/v1/admin/products", headers=author.headers, json=_product(code)).status_code == 403
    assert client.post("/v1/admin/products", headers=no_mfa.headers, json=_product(code)).status_code == 403

    made = client.post("/v1/admin/products", headers=finance.headers, json=_product(code))
    assert made.status_code == 201, made.text
    p = made.json()
    assert p["status"] == "draft" and p["scope"] == {"grades": [11], "subjects": ["biology"], "exams": []}
    assert made.headers["cache-control"] == "private, no-store"
    assert client.post("/v1/admin/products", headers=finance.headers, json=_product(code)).status_code == 409
    assert client.get("/v1/products").json() == [x for x in client.get("/v1/products").json() if x["code"] != code]

    edited = client.put(f"/v1/admin/products/{p['id']}", headers=finance.headers, json=_product(code, written_units=6))
    assert edited.status_code == 200 and edited.json()["written_units"] == 6
    reason = {"reason": "Fixture: ready for a test listing"}
    on = client.post(f"/v1/admin/products/{p['id']}/activate", headers=finance.headers, json=reason)
    assert on.status_code == 200 and on.json()["status"] == "active"
    frozen = client.put(f"/v1/admin/products/{p['id']}", headers=finance.headers, json=_product(code, duration_days=30))
    assert frozen.status_code == 409 and frozen.json()["code_reason"] == "PRODUCT_FROZEN"

    url = f"/v1/admin/products/{p['id']}/prices"
    assert client.post(url, headers=finance.headers, json=_price(2500.5)).status_code == 422  # minor units only
    assert client.post(url, headers=finance.headers, json={**_price(), "currency": "pkr"}).status_code == 422
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    assert client.post(url, headers=finance.headers, json=_price(starts_at=past)).status_code == 422
    first = client.post(url, headers=finance.headers, json=_price())
    assert first.status_code == 201 and first.json()["current_price"]["amount_minor"] == 250_000
    later = (datetime.now(UTC) + timedelta(days=7)).isoformat()
    queued = client.post(url, headers=finance.headers, json=_price(300_000, starts_at=later)).json()
    assert queued["current_price"]["amount_minor"] == 250_000  # a future price doesn't apply early
    assert [h["amount_minor"] for h in queued["price_history"]] == [250_000, 300_000]  # nothing overwritten

    listed = client.get("/v1/products")
    assert listed.headers["cache-control"].startswith("public")
    mine = next(x for x in listed.json() if x["code"] == code)
    assert mine["price"] == {
        "channel": "web",
        "currency": "PKR",
        "amount_minor": 250_000,
        "on_sale": True,
        "starts_at": mine["price"]["starts_at"],
        "reason": None,  # staff notes stay private
    }
    assert mine["written_units"] == 6 and "status" not in mine and "id" not in mine

    withdraw = client.post(
        url, headers=finance.headers, json=_price(None, on_sale=False, reason="Fixture: pause sales")
    )
    assert withdraw.status_code == 201
    assert next(x for x in client.get("/v1/products").json() if x["code"] == code)["price"] is None
    off = client.post(f"/v1/admin/products/{p['id']}/retire", headers=finance.headers, json=reason)
    assert off.status_code == 200 and off.json()["status"] == "retired"
    assert all(x["code"] != code for x in client.get("/v1/products").json())
    assert client.post(url, headers=finance.headers, json=_price()).status_code == 409
    actions = (
        db.execute(
            text("select action from audit_event where target_type = 'product' and target_id = :i order by at"),
            {"i": p["id"]},
        )
        .scalars()
        .all()
    )
    assert actions[:3] == ["product.created", "product.updated", "product.activated"]
    assert actions.count("product.price_set") == 3 and actions[-1] == "product.retired"


def test_scope_follows_the_catalogue_and_the_trial_is_not_a_product(client: TestClient, db: Session) -> None:
    finance = Staff(client, db, ["finance"], None, mfa=True)
    owner = Staff(client, db, ["owner_admin"], None, mfa=True)

    def make(body: dict[str, Any]) -> Any:
        return client.post("/v1/admin/products", headers=finance.headers, json=body)

    no_book = make(_product(_code("x"), scope={"grades": [11], "subjects": ["astrology"]}))
    assert no_book.status_code == 422 and "no book" in no_book.json()["detail"]
    assert make(_product(_code("x"), scope={"grades": [10], "subjects": ["biology"]})).status_code == 422
    assert make(_product(_code("x"), scope={"subjects": ["biology"]})).status_code == 422  # name the class
    assert make(_product(_code("x"), kind="platform")).status_code == 422  # the platform covers everything
    platform = make(_product(_code("all"), kind="platform", scope={}))
    assert platform.status_code == 201 and platform.json()["scope"] == {}
    trial = make(_product(f"fx-trial-{uuid.uuid4().hex[:6]}", kind="platform", scope={}))
    assert trial.status_code == 422 and trial.json()["code_reason"] == "TRIAL_NOT_PRODUCT"

    exam = f"FX-EXAM-{uuid.uuid4().hex[:6].upper()}"
    assert make(_product(_code("ex"), kind="exam_package", scope={"exams": [exam]})).status_code == 422
    made = client.post(
        "/v1/admin/exam-profiles",
        headers=owner.headers,
        json={"code": exam, "name": "Fixture exam profile", "eligibility_note": "Technical fixture."},
    )
    assert made.status_code == 201, made.text
    assert make(_product(_code("ex"), kind="exam_package", scope={"exams": [exam]})).status_code == 201
    one = {"grades": [11], "subjects": ["biology"]}
    assert make(_product(_code("b"), kind="bundle", scope=one)).status_code == 422  # a bundle combines two or more
    both = make(_product(_code("b"), kind="bundle", scope={"grades": [11, 12], "subjects": ["chemistry", "biology"]}))
    assert both.status_code == 201 and both.json()["scope"]["subjects"] == ["biology", "chemistry"]
