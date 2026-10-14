"""P04.S2.T3 (ACCESS-GRANTS-01): granters manage staff grants (scholarship, promotional, pilot) from a list.

The list shows each grant's learner, terms, reason and the written units it has funded, newest first; revoked grants
leave the current list but stay on record with their reason. Only granters with MFA see it. Labelled fixture accounts.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from portal_api.db import get_sessionmaker
from tests.test_content_workflow import Staff
from tests.test_written_attempts import _learner, _start

URL = "/v1/admin/entitlements"


def _mine(rows: list[dict[str, Any]], email: str) -> list[dict[str, Any]]:
    return [r for r in rows if r["email"] == email]


def test_granters_see_their_grants_with_units_used_and_revocations_on_record(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    with get_sessionmaker()() as db:
        finance = Staff(client, db, ["finance"], mfa=True)
        no_mfa = Staff(client, db, ["finance"])
    learner = _learner(client)
    granted = client.post(
        URL,
        headers=finance.headers,
        json={
            "email": learner.email,
            "source": "pilot",
            "days": 7,
            "written_units": 6,
            "reason": "Fixture: pilot cohort",
        },
    )
    assert granted.status_code == 201, granted.text

    [row] = _mine(client.get(URL, headers=finance.headers).json(), learner.email)
    assert (row["source"], row["written_units"], row["units_consumed"], row["units_held"]) == ("pilot", 6, 0, 0)
    assert row["reason"] == "Fixture: pilot cohort" and row["status"] == "active"

    _start(client, learner, published_written["chapter"])  # the grant ending first funds the test
    [row] = _mine(client.get(URL, headers=finance.headers).json(), learner.email)
    assert row["units_held"] >= 1 and row["units_consumed"] == 0

    revoked = client.post(
        f"{URL}/{row['id']}/revoke", headers=finance.headers, json={"reason": "Fixture: left the pilot"}
    )
    assert revoked.status_code == 200, revoked.text
    assert _mine(client.get(URL, headers=finance.headers).json(), learner.email) == []  # not current any more
    everything = client.get(URL, params={"current": "false", "source": "pilot"}, headers=finance.headers).json()
    [kept] = _mine(everything, learner.email)
    assert (kept["status"], kept["revoke_reason"]) == ("revoked", "Fixture: left the pilot")

    assert client.get(URL, headers=learner.headers).status_code == 403
    assert client.get(URL, headers=no_mfa.headers).status_code == 403
