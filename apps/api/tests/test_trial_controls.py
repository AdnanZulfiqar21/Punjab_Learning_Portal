"""P14.S8.T2 (TRIAL-CONTROLS-01): the trial keeps no hardware identity.

Trial tables have no column for a hardware identifier, advertising ID, phone number, address or raw attestation
token. Whatever a client sends in its device proof, only the adapter's verdict is stored, and the installation is
kept as a peppered hash, never the token itself. Proof values here are labelled fixtures.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import text

from portal_api.db import Base, get_sessionmaker
from tests.test_trial_claims import _claim, _install, _user

FORBIDDEN = (
    "imei",
    "serial",
    "android_id",
    "advertis",
    "idfa",
    "idfv",
    "mac_address",
    "hardware",
    "fingerprint",
    "phone",
    "ip_address",
    "attestation_token",
    "raw_token",
    "install_token",
)


def test_trial_tables_have_no_hardware_identity_columns() -> None:
    trial = {name: t for name, t in Base.metadata.tables.items() if name.startswith("trial_")}
    assert {"trial_claim", "trial_device_use", "trial_exception", "trial_grant"} <= set(trial)
    found = [f"{n}.{c.name}" for n, t in trial.items() for c in t.columns if any(w in c.name for w in FORBIDDEN)]
    assert found == []


def test_only_the_verdict_is_kept_from_a_device_proof(client: TestClient) -> None:
    who, install = _user(client), _install()
    sent = {"imei": "FIXTURE-IMEI-0042", "serial": "FIXTURE-SERIAL-7", "attestation_token": "FIXTURE-TOKEN-ABC"}
    assert _claim(client, who, install, **sent).json()["state"] == "granted"
    with get_sessionmaker()() as db:
        rows = db.execute(
            text(
                "select c.evidence::text, c.installation_ref, d.evidence::text, d.installation_ref "
                "from trial_claim c join trial_device_use d on d.user_id = c.user_id where c.user_id = :u"
            ),
            {"u": str(who.id)},
        ).one()
    stored = json.dumps([str(x) for x in rows])
    for value in (*sent.values(), install):
        assert value not in stored, value
    assert set(json.loads(rows[0])) <= {
        "adapter",
        "verdict",
        "detail",
        "mode",
        "mark",
    }  # mark: the marker write outcome
