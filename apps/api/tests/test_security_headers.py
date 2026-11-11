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


def test_nul_in_query_is_refused_with_headers(client: TestClient) -> None:
    # SECURITY-HARDEN-01: a NUL character in a query parameter used to reach the database driver and come back as a
    # bare 500 text/plain without these headers; it is refused as a 422 problem response instead.
    for path in ("/v1/search?q=ab%00cd", "/v1/help/articles?q=ab%00cd"):
        r = client.get(path)
        assert r.status_code == 422, path
        assert r.headers["content-type"].startswith("application/problem+json"), path
        assert r.headers["x-content-type-options"] == "nosniff", path
        assert "default-src 'none'" in r.headers["content-security-policy"], path


def test_unhandled_error_is_a_problem_with_headers() -> None:
    # SECURITY-HARDEN-01: any unexpected error is answered as problem+json with the defensive headers, never as the
    # framework's bare text page.
    from portal_api.main import create_app

    app = create_app()

    @app.get("/__boom")
    def boom() -> None:
        raise RuntimeError("boom")

    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/__boom")
    assert r.status_code == 500
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["title"] == "INTERNAL_ERROR"
    assert "boom" not in r.text
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'none'" in r.headers["content-security-policy"]
