"""R08: the development issuer must be created once per process, even when the first requests arrive together.

Before the fix, concurrent first calls each generated their own RSA key; `lru_cache` kept one, so tokens signed with
the other key failed verification (a 401 straight after a successful sign-up). Development/test adapter only.
"""

from __future__ import annotations

import threading

from portal_api.modules.identity import tokens


def _race_once(n: int = 8) -> list[str]:
    tokens.reset_dev_issuer()
    barrier = threading.Barrier(n)
    issued: list[str] = []
    lock = threading.Lock()

    def sign_up(i: int) -> None:
        barrier.wait()
        token = tokens.get_dev_issuer().issue(f"dev|race-{i}", None)
        with lock:
            issued.append(token)

    threads = [threading.Thread(target=sign_up, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return issued


def test_concurrent_first_use_yields_one_issuer_and_valid_tokens() -> None:
    for _ in range(3):
        for token in _race_once():
            tokens.verify(token)  # raises InvalidToken if signed by an orphaned key
