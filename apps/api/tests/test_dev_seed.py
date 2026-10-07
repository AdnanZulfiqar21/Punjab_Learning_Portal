"""Development staff fixtures (portal-dev-seed-staff): idempotent, scoped, and refused without the dev adapter."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from portal_api.config import get_settings
from portal_api.db import get_engine, get_sessionmaker
from portal_api.modules.identity import dev_seed
from portal_api.modules.identity.models import AppUser, StaffRoleGrant


def _clear() -> None:
    get_settings.cache_clear()
    get_sessionmaker.cache_clear()
    get_engine.cache_clear()


def test_seed_is_idempotent_and_scoped(client: TestClient, db: Session) -> None:
    assert dev_seed.main([]) == 0
    assert dev_seed.main([]) == 0  # second run adds nothing
    for email, roles in dev_seed.FIXTURES:
        user = db.scalar(select(AppUser).where(AppUser.email == email))
        assert user is not None
        grants = db.scalars(
            select(StaffRoleGrant).where(StaffRoleGrant.user_id == user.id, StaffRoleGrant.revoked_at.is_(None))
        ).all()
        assert sorted(g.role for g in grants) == sorted(roles)
        assert all(g.scope == dev_seed.SCOPE for g in grants)
    total = db.scalar(select(func.count()).select_from(AppUser).where(AppUser.email.like("studio-%@example.com")))
    assert total == len(dev_seed.FIXTURES)
    # The fixtures sign in through the development adapter only.
    tok = client.post(
        "/v1/dev-auth/token", json={"email": "studio-reviewer@example.com", "password": dev_seed.FIXTURE_PASSWORD}
    )
    assert tok.status_code == 200


def test_seed_refuses_without_the_dev_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORTAL_DEV_AUTH_ENABLED", "false")
    _clear()
    try:
        assert dev_seed.main([]) == 2
    finally:
        monkeypatch.undo()
        _clear()
