from __future__ import annotations

from fastapi.testclient import TestClient


def test_hosted_cors_allows_only_configured_frontend_origin(monkeypatch) -> None:
    monkeypatch.setenv("SCREENER_HOSTED_MODE", "1")
    monkeypatch.setenv("SCREENER_OWNER_SECRET", "owner-secret")
    monkeypatch.setenv("SCREENER_FRONTEND_ORIGIN", "https://owner.example")

    from backend.src.api.app import create_app

    client = TestClient(create_app())

    allowed = client.options(
        "/strategies",
        headers={
            "Origin": "https://owner.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    denied = client.options(
        "/strategies",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "https://owner.example"
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers
