"""P18.S3.T1 (MINIMISATION-01): the profile stores only explicit, purposeful fields, and photos keep no location or
camera metadata. Synthetic images and fixture accounts only."""

from __future__ import annotations

import io

from fastapi.testclient import TestClient
from PIL import Image

from portal_api.db import Base
from tests.test_support_attachments import _attach, _staff, _ticket

PROFILE_FIELDS = {
    "user_id",
    "grade",
    "stream",
    "subjects",
    "target_exams",
    "target_year",
    "explanation_language",
    "daily_minutes",
    "updated_at",
}


def test_the_learner_profile_has_no_free_form_store() -> None:
    columns = {c.name for c in Base.metadata.tables["student_profile"].columns}
    assert columns == PROFILE_FIELDS  # a new personal field needs a reason in docs/security/data-minimisation.md


def _jpeg_with_gps() -> bytes:
    exif = Image.Exif()
    exif[0x010F] = "FixtureCam"  # Make
    exif[0x8825] = {1: "N", 2: (31.0, 33.0, 0.0), 3: "E", 4: (74.0, 21.0, 0.0)}  # GPS: a fixture location
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), color=(120, 130, 140)).save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


def test_a_photo_keeps_no_location_or_camera_metadata(client: TestClient) -> None:
    original = _jpeg_with_gps()
    assert b"FixtureCam" in original and Image.open(io.BytesIO(original)).getexif().get_ifd(0x8825)
    learner = _staff(client, [])
    t = _ticket(client, learner)
    r = _attach(client, learner, t["id"], original)
    assert r.status_code == 201, r.text
    stored = client.get(f"/v1/support/tickets/{t['id']}/attachments/{r.json()['id']}", headers=learner.headers).content
    assert b"FixtureCam" not in stored and b"Exif" not in stored
    assert not Image.open(io.BytesIO(stored)).getexif()
