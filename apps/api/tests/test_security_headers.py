"""P18.S2.T1 (HEADERS-01): API responses carry defensive security headers."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_api_responses_carry_security_headers(client: TestClient) -> None:
    for path in ("/healthz", "/v1/catalogue", "/v1/me"):  # ok, public data, and a 401 problem response
        r = client.get(path)
        assert r.headers["x-content-type-options"] == "nosniff", path
        assert r.headers["x-frame-options"] == "DENY", path
        assert r.headers["referrer-policy"] == "no-referrer", path
        assert "frame-ancestors 'none'" in r.headers["content-security-policy"], path
        assert "default-src 'none'" in r.headers["content-security-policy"], path
