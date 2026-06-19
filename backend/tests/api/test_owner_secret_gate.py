from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _hosted_client(monkeypatch: pytest.MonkeyPatch, secret: str = "owner-secret") -> TestClient:
    monkeypatch.setenv("SCREENER_HOSTED_MODE", "1")
    monkeypatch.setenv("SCREENER_OWNER_SECRET", secret)
    monkeypatch.setenv("SCREENER_FRONTEND_ORIGIN", "https://owner.example")

    from backend.src.api.app import create_app

    return TestClient(create_app())


@pytest.mark.parametrize(
    "path",
    [
        "/strategies",
        "/candidates/ABC",
        "/data/freshness",
        "/regime",
    ],
)
def test_hosted_mode_rejects_missing_owner_secret(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    client = _hosted_client(monkeypatch)

    response = client.get(path)

    assert response.status_code == 401
    assert "strategies" not in response.text
    assert "candidates" not in response.text
    assert "sources" not in response.text
    assert "regime" not in response.text


def test_hosted_mode_rejects_wrong_owner_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _hosted_client(monkeypatch)

    response = client.get("/strategies", headers={"X-Owner-Secret": "wrong"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_hosted_mode_allows_correct_owner_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _hosted_client(monkeypatch)

    response = client.get("/strategies", headers={"X-Owner-Secret": "owner-secret"})

    assert response.status_code == 200
    body = response.json()
    assert "strategies" in body
    assert "data_as_of" in body
    assert "disclaimer" in body


def test_hosted_mode_without_owner_secret_refuses_to_build_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCREENER_HOSTED_MODE", "1")
    monkeypatch.delenv("SCREENER_OWNER_SECRET", raising=False)

    from backend.src.api.app import create_app

    with pytest.raises(RuntimeError, match="SCREENER_OWNER_SECRET"):
        create_app()


def test_local_mode_leaves_owner_secret_gate_inactive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCREENER_HOSTED_MODE", "0")
    monkeypatch.delenv("SCREENER_OWNER_SECRET", raising=False)

    from backend.src.api.app import create_app

    response = TestClient(create_app()).get("/strategies")

    assert response.status_code == 200
    assert "strategies" in response.json()
