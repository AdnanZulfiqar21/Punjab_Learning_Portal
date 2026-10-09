"""Learner reports run a fixed number of queries, however long the learner's history (review OCT9 follow-up).
Technical fixture questions only."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.engine import Engine

from tests.test_attempts import POOL, _form, _learner, _start
from tests.test_mistake_notebook import _answer, _submit


@contextmanager
def _queries() -> Iterator[list[str]]:
    seen: list[str] = []

    def count(_conn: Any, _cursor: Any, statement: str, *_: Any) -> None:
        seen.append(statement)

    event.listen(Engine, "before_cursor_execute", count)
    try:
        yield seen
    finally:
        event.remove(Engine, "before_cursor_execute", count)


def _sit(client: TestClient, who: Any, physics: dict[str, Any]) -> None:
    form = _form(client, who, physics["chapter"], count=POOL).json()
    attempt = _start(client, who, form["id"])
    _answer(client, who, form["id"], attempt, correct={1, 2})
    _submit(client, who, attempt["id"])


def test_evidence_and_progress_queries_do_not_grow_with_history(client: TestClient, physics: dict[str, Any]) -> None:
    learner = _learner(client)
    _sit(client, learner, physics)
    counts = []
    for extra in (0, 3):
        for _ in range(extra):
            _sit(client, learner, physics)
        with _queries() as q:
            assert (
                client.get(
                    "/v1/me/evidence", headers=learner.headers, params={"grade": 11, "subject": "physics"}
                ).status_code
                == 200
            )
            assert client.get("/v1/me/progress", headers=learner.headers).status_code == 200
        counts.append(len(q))
    assert counts[0] == counts[1], counts
