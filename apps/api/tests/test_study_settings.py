"""P04.S3.T2 (SETTINGS-01): a learner's usual study settings. Unsaved settings come back as the defaults; a change
touches only the settings it names, so two devices changing different settings never undo each other; settings are
private to their account and included in the personal data export."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.test_content_workflow import Staff


def test_settings_start_as_defaults_and_change_one_at_a_time(client: TestClient, db: Session) -> None:
    learner = Staff(client, db, [])
    first = client.get("/v1/me/settings", headers=learner.headers)
    assert first.status_code == 200 and first.headers["cache-control"] == "private, no-store"
    assert first.json() == {
        "theme": "system",
        "text_size": "default",
        "reduce_motion": False,
        "data_saver": False,
        "video_quality": "auto",
        "saved": False,
        "updated_at": None,
    }

    # One device turns on the data saver; another changes the theme. Neither undoes the other.
    phone = client.patch("/v1/me/settings", headers=learner.headers, json={"data_saver": True})
    assert phone.status_code == 200 and phone.json()["data_saver"] and phone.json()["saved"]
    laptop = client.patch("/v1/me/settings", headers=learner.headers, json={"theme": "dark", "text_size": "large"})
    assert laptop.status_code == 200
    now = client.get("/v1/me/settings", headers=learner.headers).json()
    assert (now["data_saver"], now["theme"], now["text_size"], now["video_quality"]) == (True, "dark", "large", "auto")
    assert now["updated_at"] is not None

    for bad in ({}, {"theme": "purple"}, {"text_size": "huge"}, {"video_quality": "8k"}, {"font": "serif"}):
        assert client.patch("/v1/me/settings", headers=learner.headers, json=bad).status_code == 422, bad

    # Settings belong to one account.
    other = Staff(client, db, [])
    assert client.get("/v1/me/settings", headers=other.headers).json()["saved"] is False
    assert client.get("/v1/me/settings").status_code == 401


def test_settings_are_in_the_personal_data_export(client: TestClient, db: Session) -> None:
    learner = Staff(client, db, [])
    assert client.patch("/v1/me/settings", headers=learner.headers, json={"reduce_motion": True}).status_code == 200
    export = client.get("/v1/me/data-export", headers=learner.headers)
    assert export.status_code == 200, export.text
    settings = json.loads(export.content)["settings"]
    assert len(settings) == 1 and settings[0]["reduce_motion"] is True and settings[0]["theme"] == "system"
