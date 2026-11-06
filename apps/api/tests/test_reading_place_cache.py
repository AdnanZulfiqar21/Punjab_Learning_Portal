"""READING-PLACE-CACHE-01: a topic's catalogue place is kept per process for a short while; access never is."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from portal_api.config import get_settings
from portal_api.errors import NotFound
from portal_api.modules.content import reading
from portal_api.modules.curriculum.models import Topic


@pytest.fixture
def place_cache(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("PORTAL_READING_PLACE_CACHE_S", "60")
    get_settings.cache_clear()
    reading.forget_places()
    yield
    reading.forget_places()
    get_settings.cache_clear()


def _a_topic(db: Session) -> Topic:
    rows = db.scalars(select(Topic).where(Topic.retired_at.is_(None)).limit(50))
    topic = next((t for t in rows if not t.practice_only), None)
    assert topic is not None
    return topic


def test_the_place_is_read_once_then_reused(loaded_db: None, db: Session, place_cache: None) -> None:
    topic = _a_topic(db)
    first = reading.reading(db, None, topic.id, None)
    calls = {"n": 0}
    real = reading._place

    def counting(session: Session, topic_id: uuid.UUID):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return real(session, topic_id)

    reading._place = counting  # type: ignore[assignment]
    try:
        again = reading.reading(db, None, topic.id, None)
    finally:
        reading._place = real  # type: ignore[assignment]
    assert calls["n"] == 0
    assert again == first
    assert (again.previous_topic_id, again.next_topic_id) == (first.previous_topic_id, first.next_topic_id)


def test_off_reads_the_catalogue_every_time(loaded_db: None, db: Session) -> None:
    assert get_settings().reading_place_cache_s == 0  # the test suite runs with the cache off
    topic = _a_topic(db)
    reading.reading(db, None, topic.id, None)
    assert reading._places == {}


def test_an_unknown_topic_is_not_cached(loaded_db: None, db: Session, place_cache: None) -> None:
    missing = uuid.uuid4()
    with pytest.raises(NotFound):
        reading.reading(db, None, missing, None)
    assert missing not in reading._places
