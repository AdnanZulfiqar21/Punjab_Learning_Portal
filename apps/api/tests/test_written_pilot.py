"""W08.S1.T1 (PILOT-R0-01): the R0 teacher-reviewed pilot switch.

* Deployed roles default to the pilot (no later written release level is qualified yet); development and test default
  to open, and an explicit setting wins either way.
* During the pilot, written practice is offered only to learners with an active pilot entitlement: availability says
  so, and building, linking and starting a written test are refused for everyone else. A paid or trial plan's units
  never fund a pilot test, and a learner's existing tests carry on.

Real PostgreSQL; technical fixture questions and labelled fixture accounts only.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from portal_api.config import Role, Settings, get_settings
from portal_api.db import get_sessionmaker
from portal_api.modules.access import service as access
from portal_api.modules.access.models import AllowanceEvent, Entitlement
from tests.test_content_workflow import Staff
from tests.test_linked_attempts import _link
from tests.test_written_attempts import _form, _learner, _png, _upload
from tests.test_written_marking import _sealed_script


def test_deployed_roles_default_to_the_pilot() -> None:
    def pilot(**kw: Any) -> bool:
        return Settings.model_construct(**kw).written_pilot_only

    assert pilot(role=Role.production) and pilot(role=Role.staging)
    assert not pilot(role=Role.development) and not pilot(role=Role.test)
    assert not pilot(role=Role.production, written_release="open")  # an explicit owner decision wins
    assert pilot(role=Role.development, written_release="r0_pilot")


def _grant(client: TestClient, learner: Staff, units: int) -> uuid.UUID:
    with get_sessionmaker()() as db:
        operator = Staff(client, db, [])
        ent = access.grant_entitlement(
            db,
            operator.id,
            learner.id,
            source="pilot",
            days=30,
            written_units=units,
            reason="Fixture: R0 pilot cohort member",
        )
        return ent.id


def _reservations(learner: Staff) -> list[AllowanceEvent]:
    with get_sessionmaker()() as db:
        return list(
            db.scalars(
                select(AllowanceEvent).where(AllowanceEvent.user_id == learner.id, AllowanceEvent.kind == "RESERVED")
            )
        )


def _access(client: TestClient, who: Staff) -> dict[str, Any]:
    r = client.get("/v1/me/access", headers=who.headers)
    assert r.status_code == 200, r.text
    return dict(r.json())


def _availability(client: TestClient, who: Staff) -> dict[str, Any]:
    r = client.get("/v1/written/availability?grade=12&subject=chemistry", headers=who.headers)
    assert r.status_code == 200, r.text
    return dict(r.json())


def test_the_r0_pilot_admits_and_funds_only_pilot_learners(
    client: TestClient, published_written: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    chapter = published_written["chapter"]
    learner = _learner(client)  # a trial plan with written-marking units
    form = _form(client, learner, chapter)
    assert form.status_code == 201
    other = _form(client, learner, chapter).json()["id"]
    started = client.post(f"/v1/written/forms/{other}/attempt", headers=learner.headers)
    assert started.status_code == 200
    sealed_by, sealed = _sealed_script(client, chapter)
    before = len(_reservations(learner))
    assert _availability(client, learner)["pilot_only"] is False
    assert (
        _access(client, learner)["written_pilot_only"] is False
        and _access(client, learner)["written_allowance"]["granted"] > 0
    )

    monkeypatch.setattr(get_settings(), "written_release", "r0_pilot")
    av = _availability(client, learner)
    assert (av["pilot_only"], av["in_pilot"]) == (True, False)
    # The plan and the price list say so too: no usable written units outside the pilot.
    plan = _access(client, learner)
    assert plan["written_pilot_only"] is True and plan["written_allowance"]["granted"] == 0
    assert plan["written_allowance"]["available"] == 0 and plan["has_access"] is True  # practice tests still open
    assert all(p["written_pilot_only"] for p in client.get("/v1/products").json())
    refused = [
        _form(client, learner, chapter),
        client.post(f"/v1/written/forms/{form.json()['id']}/attempt", headers=learner.headers),
        _link(client, sealed_by, sealed["id"], reason="REWRITE", positions=[1]),
    ]
    for r in refused:
        assert r.status_code == 403 and r.json()["title"] == "WRITTEN_PILOT_ONLY", r.text
        assert "pilot" in r.json()["detail"]
    assert len(_reservations(learner)) == before  # nothing was reserved from the trial plan
    # a test started before the pilot began carries on
    page = _upload(client, learner, started.json()["id"], _png(seed=int(uuid.uuid4().int % 250)))
    assert page.status_code == 201, page.text

    pilot_without_units = _grant(client, learner, 0)
    assert _availability(client, learner)["in_pilot"] is True
    unfunded = client.post(f"/v1/written/forms/{form.json()['id']}/attempt", headers=learner.headers)
    assert unfunded.status_code == 403 and unfunded.json()["title"] == "ALLOWANCE_EXHAUSTED"
    assert unfunded.json()["available"] == 0  # the trial's units don't count during the pilot
    assert len(_reservations(learner)) == before

    funded_by = _grant(client, learner, 6)
    assert _access(client, learner)["written_allowance"]["granted"] == 6  # only the pilot's units
    attempt = client.post(f"/v1/written/forms/{form.json()['id']}/attempt", headers=learner.headers)
    assert attempt.status_code == 200, attempt.text
    new = [e for e in _reservations(learner) if str(e.attempt_id) == attempt.json()["id"]]
    assert [e.entitlement_id for e in new] == [funded_by]  # the pilot entitlement, never the trial
    with get_sessionmaker()() as db:
        assert db.get(Entitlement, pilot_without_units) is not None
        sources = {e.source for e in access.active_entitlements(db, learner.id, access.db_now(db))}
    assert sources == {"trial", "pilot"}
