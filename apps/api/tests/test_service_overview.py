"""P16.S1.T3 (SERVICE-OVERVIEW-01): request error rate, latency and submission success join the operator signals, each
with thresholds, an owner and a runbook; what can't be measured yet (video, device journeys) says so,
with its blocker."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from portal_api import observability
from tests.test_content_workflow import Staff


def test_request_window_summarises_errors_latency_and_submissions() -> None:
    observability.reset_window()
    for ms in (10, 20, 30, 40, 1000):
        observability.record_request("/v1/catalogue", 200, ms)
    observability.record_request("/v1/catalogue", 503, 50)
    observability.record_request("/v1/attempts/{attempt_id}/submit", 200, 30)
    observability.record_request("/v1/attempts/{attempt_id}/submit", 500, 30)
    observability.record_request("/v1/written-attempts/{attempt_id}/seal", 409, 30)  # a refusal, not a failure
    s = observability.window_summary()
    assert s["requests"] == 9 and s["server_errors"] == 2
    assert round(s["server_error_ratio"], 3) == round(2 / 9, 3)
    assert s["latency_p95_ms"] == 1000 and s["latency_p50_ms"] == 30
    assert s["submissions"] == 3 and round(s["submission_server_error_ratio"], 3) == round(1 / 3, 3)


def test_service_signals_are_listed_with_runbooks_and_honest_gaps(client: TestClient, db: Session) -> None:
    observability.reset_window()
    operator = Staff(client, db, ["platform_operator"], mfa=True)
    assert client.get("/v1/catalogue").status_code == 200  # recorded by the middleware
    signals = {s["name"]: s for s in client.get("/v1/ops/signals", headers=operator.headers).json()}
    for name in ("http_server_error_ratio_5m", "http_latency_p95_ms_5m", "submission_server_error_ratio_5m"):
        assert signals[name]["available"] is True and signals[name]["runbook"].startswith("docs/runbooks/alerts.md#")
    assert signals["http_server_error_ratio_5m"]["level"] == "ok"
    for name, blocker in (("video_playback_failure_ratio", "B05"), ("device_journey_budget_breaches", "B09")):
        assert signals[name]["available"] is False and signals[name]["blocker"] == blocker
        assert signals[name]["level"] == "unavailable"
