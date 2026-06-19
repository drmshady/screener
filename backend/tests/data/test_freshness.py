from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from backend.src.data.freshness import compute_data_freshness


def _write_manifest(path: Path, sources: dict) -> None:
    path.write_text(json.dumps({"sources": sources}, indent=2), encoding="utf-8")


def test_freshness_uses_trading_sessions_across_us_holiday_weekend(tmp_path: Path):
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(
        manifest_path,
        {
            "yfinance": {
                "kind": "prices",
                "refresh_interval_days": 0,
                "is_stale": False,
                "source_as_of": "2026-07-02T21:00:00Z",
                "last_bar_date_by_ticker": {"AAPL": "2026-07-02"},
            }
        },
    )

    sunday_snapshot = compute_data_freshness(
        manifest_path=manifest_path,
        now=datetime(2026, 7, 5, 12, tzinfo=timezone.utc),
    )
    sunday_record = sunday_snapshot.sources[0]
    assert sunday_snapshot.latest_session == date(2026, 7, 2)
    assert sunday_record.data_as_of == date(2026, 7, 2)
    assert sunday_record.sessions_behind == 0
    assert sunday_record.is_stale is False

    monday_snapshot = compute_data_freshness(
        manifest_path=manifest_path,
        now=datetime(2026, 7, 6, 23, tzinfo=timezone.utc),
    )
    monday_record = monday_snapshot.sources[0]
    assert monday_snapshot.latest_session == date(2026, 7, 6)
    assert monday_record.sessions_behind == 1
    assert monday_record.is_stale is True


def test_missing_required_source_is_reported_stale(tmp_path: Path):
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(
        manifest_path,
        {
            "yfinance": {
                "kind": "prices",
                "source_as_of": "2026-07-06T21:00:00Z",
                "last_bar_date_by_ticker": {"AAPL": "2026-07-06"},
            }
        },
    )

    snapshot = compute_data_freshness(
        manifest_path=manifest_path,
        now=datetime(2026, 7, 6, 23, tzinfo=timezone.utc),
        required_sources=("yfinance", "sec_edgar_company_tickers"),
    )

    missing = next(
        source
        for source in snapshot.sources
        if source.source_name == "sec_edgar_company_tickers"
    )
    assert missing.kind == "unknown"
    assert missing.data_as_of is None
    assert missing.sessions_behind is None
    assert missing.is_stale is True
    assert snapshot.any_stale is True


def test_any_stale_is_or_and_helper_does_not_mutate_manifest(tmp_path: Path):
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(
        manifest_path,
        {
            "yfinance": {
                "kind": "prices",
                "refresh_interval_days": 1,
                "source_as_of": "2026-07-06T21:00:00Z",
                "last_bar_date_by_ticker": {"AAPL": "2026-07-06"},
            },
            "ticker_profile_cache": {
                "kind": "fundamentals",
                "refresh_interval_days": 7,
                "source_as_of": "2026-06-01T00:00:00Z",
            },
        },
    )
    before = manifest_path.read_text(encoding="utf-8")

    first = compute_data_freshness(
        manifest_path=manifest_path,
        now=datetime(2026, 7, 6, 23, tzinfo=timezone.utc),
    )
    second = compute_data_freshness(
        manifest_path=manifest_path,
        now=datetime(2026, 7, 6, 23, tzinfo=timezone.utc),
    )

    assert first == second
    assert manifest_path.read_text(encoding="utf-8") == before
    assert {source.source_name: source.is_stale for source in first.sources} == {
        "ticker_profile_cache": True,
        "yfinance": False,
    }
    assert first.any_stale is True
