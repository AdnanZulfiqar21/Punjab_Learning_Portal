"""CORS: a browser build of the app (Expo web) may send every header the app's API client sends."""

from fastapi.testclient import TestClient


def test_preflight_allows_the_app_headers(client: TestClient) -> None:
    res = client.options(
        "/v1/topics/00000000-0000-0000-0000-000000000000/lesson",
        headers={
            "Origin": "http://localhost:8190",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "cache-control,authorization,x-portal-client",
        },
    )
    assert res.status_code == 200
    allowed = res.headers["access-control-allow-headers"].lower()
    assert "cache-control" in allowed
