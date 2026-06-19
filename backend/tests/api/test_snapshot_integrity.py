from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.src.data.snapshot import check_snapshot_integrity
from backend.src.lib import hosting


def _build_snapshot(root: Path) -> None:
    """Materialize a complete read-only snapshot scope under ``root``."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_text(
        json.dumps({"sources": {"yfinance": {"kind": "prices"}}}), encoding="utf-8"
    )
    parquet = root / "prices" / "parquet" / "year=2026"
    parquet.mkdir(parents=True, exist_ok=True)
    (parquet / "part-0.parquet").write_bytes(b"PAR1payload")
    con = sqlite3.connect(str(root / "catalog.db"))
    con.execute("CREATE TABLE backtest_runs (id INTEGER)")
    con.commit()
    con.close()
    edgar = root / "edgar_cache"
    edgar.mkdir()
    (edgar / "AAPL.json").write_text("{}", encoding="utf-8")
    (root / "econ_calendar.yaml").write_text("events: []", encoding="utf-8")


def test_complete_snapshot_is_healthy(tmp_path: Path) -> None:
    _build_snapshot(tmp_path)

    integrity = check_snapshot_integrity(tmp_path)

    assert integrity.ok is True
    assert integrity.manifest_ok is True
    assert integrity.missing == ()
    assert all(integrity.present.values())


@pytest.mark.parametrize(
    "remove, expected_missing",
    [
        ("manifest.json", "manifest"),
        ("prices", "prices"),
        ("catalog.db", "catalog"),
        ("edgar_cache", "edgar_cache"),
        ("econ_calendar.yaml", "calendars"),
    ],
)
def test_missing_store_marks_snapshot_unhealthy(
    tmp_path: Path, remove: str, expected_missing: str
) -> None:
    _build_snapshot(tmp_path)
    target = tmp_path / remove
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()

    integrity = check_snapshot_integrity(tmp_path)

    assert integrity.ok is False
    assert expected_missing in integrity.missing


def test_corrupt_manifest_marks_snapshot_unhealthy(tmp_path: Path) -> None:
    _build_snapshot(tmp_path)
    (tmp_path / "manifest.json").write_text("{not json", encoding="utf-8")

    integrity = check_snapshot_integrity(tmp_path)

    assert integrity.manifest_ok is False
    assert integrity.ok is False
    assert "manifest" in integrity.missing


def test_catalog_without_backtest_runs_is_unhealthy(tmp_path: Path) -> None:
    _build_snapshot(tmp_path)
    path = tmp_path / "catalog.db"
    path.unlink()
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE tickers (symbol TEXT)")
    con.commit()
    con.close()

    integrity = check_snapshot_integrity(tmp_path)

    assert integrity.ok is False
    assert "catalog" in integrity.missing


def _hosted_client(monkeypatch: pytest.MonkeyPatch, root: Path) -> TestClient:
    monkeypatch.setattr(hosting, "snapshot_root", lambda: root)
    monkeypatch.setenv("SCREENER_HOSTED_MODE", "1")
    monkeypatch.setenv("SCREENER_OWNER_SECRET", "owner-secret")
    monkeypatch.setenv("SCREENER_FRONTEND_ORIGIN", "https://owner.example")
    from backend.src.api.app import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def test_health_endpoint_ok_when_snapshot_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _build_snapshot(tmp_path)
    client = _hosted_client(monkeypatch, tmp_path)

    # No owner secret supplied: the health probe must be reachable for the platform.
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["snapshot_ok"] is True
    assert body["status"] == "ok"


def test_health_endpoint_maintenance_when_snapshot_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _build_snapshot(tmp_path)
    (tmp_path / "catalog.db").unlink()
    client = _hosted_client(monkeypatch, tmp_path)

    response = client.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["snapshot_ok"] is False
    assert body["status"] == "maintenance"
    assert "catalog" in body["missing"]
