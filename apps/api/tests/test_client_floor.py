"""P13.S1.T4 (CLIENT-FLOOR-01): publication and previews check blocks against the oldest supported build's registered
manifest, never less carefully than the code's lower bound. Fixture manifests at versions no real build uses."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from portal_api.modules.content import blocks
from portal_api.modules.system import clients
from tests.test_content_workflow import Staff


def _manifest(client: TestClient, op: Staff, version: str, renderer: int) -> None:
    body = {
        "platform": "android",
        "app_version": version,
        "renderer_version": renderer,
        "pack_format_version": 1,
        "block_types": {"paragraph": 1},
    }
    r = client.post("/v1/ops/clients/manifests", headers=op.headers, json=body)
    assert r.status_code == 201, r.text


def _minimum_now(client: TestClient, db: Session, op: Staff, version: str) -> None:
    body = {
        "min_version": version,
        "reason": "Fixture: client floor test",
        "enforce_at": (datetime.now(UTC) + timedelta(days=15)).isoformat(),
    }
    r = client.put("/v1/ops/clients/android/minimum", headers=op.headers, json=body)
    assert r.status_code == 200, r.text
    db.execute(  # the notice period has passed
        text(
            "update client_version_policy set enforce_at = now() - interval '1 minute' "
            "where platform = 'android' and min_version = :v"
        ),
        {"v": version},
    )
    db.commit()
    clients._cache.clear()


def test_the_oldest_supported_builds_manifest_sets_the_floor(client: TestClient, db: Session) -> None:
    op = Staff(client, db, ["platform_operator"], None, mfa=True)
    author = Staff(client, db, ["content_author"], {"grades": [11], "subjects": ["biology"]})
    before = clients.policy(db, "android")
    _manifest(client, op, "89.0.0", 1)  # below the minimum set next: no longer supported, so ignored
    _manifest(client, op, "90.0.0", 2)
    _manifest(client, op, "90.1.0", 3)
    try:
        _minimum_now(client, db, op, "90.0.0")
        assert clients.floor_version(db, "android") == "90.0.0"
        floor = clients.renderer_floor(db)
        assert floor["android"] == 2  # the minimum build has a manifest: its renderer is the floor
        assert floor["web"] == blocks.SUPPORTED_RENDERER["web"]  # the web app is always current
        shown = client.get("/v1/studio/block-registry", headers=author.headers).json()
        assert shown["supported_renderer"]["android"] == 2

        _minimum_now(client, db, op, "90.0.5")  # a minimum with no manifest of its own
        assert clients.renderer_floor(db)["android"] == blocks.SUPPORTED_RENDERER["android"]  # the careful lower bound
    finally:
        restore = before.min_version if before is not None else "1.0.0"
        r = client.put(
            "/v1/ops/clients/android/minimum",
            headers=op.headers,
            json={"min_version": restore, "reason": "Fixture: restore"},
        )
        assert r.status_code == 200, r.text  # lowering applies at once
        clients._cache.clear()
    assert clients.renderer_floor(db)["android"] == blocks.SUPPORTED_RENDERER["android"]


def test_checks_use_the_floor_they_are_given() -> None:
    parsed, problems = blocks.parse({"blocks": [{"type": "paragraph", "text": "Fixture"}]})
    assert parsed is not None, problems
    errors, warnings = blocks.check_renderers(parsed.blocks, for_publication=True, where="blocks")
    assert errors == warnings == []
    with blocks.client_floor({"web": 1, "android": 0, "ios": 1}):  # an android build older than every block
        assert blocks.supported_renderer()["android"] == 0
        errors, warnings = blocks.check_renderers(parsed.blocks, for_publication=True, where="blocks")
        assert errors or warnings  # the paragraph now needs a reviewed fallback on android
        assert blocks.needs_fallback("paragraph")
    assert blocks.supported_renderer() == blocks.SUPPORTED_RENDERER  # restored outside the block
