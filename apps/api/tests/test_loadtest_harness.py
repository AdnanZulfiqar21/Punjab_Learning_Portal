"""LOAD-01: the load generator's statistics and safety checks (the generator itself runs outside CI)."""

from __future__ import annotations

import pytest

from loadtest.practice_journey import Recorder, parse, percentile, report


def test_percentiles_and_report() -> None:
    assert percentile([5.0], 99) == 5.0
    values = [float(v) for v in range(1, 101)]
    assert (percentile(values, 50), percentile(values, 95), percentile(values, 99)) == (50.0, 95.0, 99.0)
    rec = Recorder()
    for ms in (10.0, 20.0, 30.0):
        rec.add("save", ms, 200)
    rec.add("save", 40.0, 503)
    rec.add("submit", 50.0, "ConnectTimeout")
    out = report(rec, {"users": 1})
    assert out["requests"] == 5 and out["server_or_transport_failures"] == 2 and out["error_rate"] == 0.4
    assert out["endpoint_mix"] == {"save": 0.8, "submit": 0.2}
    assert out["endpoints"]["save"]["statuses"] == {"200": 3, "503": 1}


def test_remote_targets_need_an_explicit_flag() -> None:
    base = ["--grade", "11", "--subject", "physics", "--chapter", "x"]
    assert parse(base).target == "http://127.0.0.1:8100"
    with pytest.raises(SystemExit):
        parse([*base, "--target", "https://staging.example.invalid"])
    assert parse([*base, "--target", "https://staging.example.invalid", "--allow-remote"]).allow_remote
