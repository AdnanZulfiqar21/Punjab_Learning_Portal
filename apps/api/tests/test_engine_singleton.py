"""R08: the database engine (and its connection pool) must be created once per process, even when the first
requests arrive together. Concurrent first calls each built an Engine with its own pool, so a cold start under load
opened several times the per-process connection budget (§5.8)."""

from __future__ import annotations

import threading

from portal_api import db as dbmod


def _race(n: int = 16) -> tuple[set[int], set[int]]:
    dbmod.reset_engine()
    barrier = threading.Barrier(n)
    engines: list[object] = []
    makers: list[object] = []
    lock = threading.Lock()

    def first_use() -> None:
        barrier.wait()
        e, m = dbmod.get_engine(), dbmod.get_sessionmaker()
        with lock:
            engines.append(e)
            makers.append(m)

    threads = [threading.Thread(target=first_use) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return {id(e) for e in engines}, {id(m) for m in makers}


def test_concurrent_first_use_creates_one_engine_and_one_sessionmaker() -> None:
    for _ in range(3):
        engines, makers = _race()
        assert len(engines) == 1 and len(makers) == 1
