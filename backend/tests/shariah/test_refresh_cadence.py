from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.src.data.shariah_halal_terminal import (
    HALAL_TERMINAL_SOURCE_NAME,
    bulk_screen_universe,
    seed_halal_terminal_results,
)
from backend.src.data.shariah_sources import load_manifest
from backend.src.shariah.refresh_cadence import freshness_status, should_refresh


NOW = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)


def test_cadence_skips_inside_window_without_calling_source(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.json"
    db = tmp_path / "catalog.db"
    manifest.write_text(
        """
        {"sources":{"halal_terminal":{
          "source_as_of":"2026-05-28T12:00:00Z",
          "refresh_interval_days":90,
          "last_row_count":7
        }}}
        """,
        encoding="utf-8",
    )

    def fetch_should_not_run(*args, **kwargs):
        raise AssertionError("Halal Terminal API should not be called inside cadence window")

    monkeypatch.setattr(
        "backend.src.data.shariah_halal_terminal.fetch_cached_results",
        fetch_should_not_run,
    )

    assert seed_halal_terminal_results(
        api_key="present",
        db_path=db,
        manifest_path=manifest,
        now=NOW,
    ) == 7


def test_cadence_refreshes_after_interval_with_key(monkeypatch):
    decision = should_refresh(
        NOW,
        NOW - timedelta(days=95),
        interval_days=90,
        key_present=True,
    )

    assert decision.action == "refresh"
    assert decision.elapsed_days == pytest.approx(95.0)


def test_cadence_marks_stale_after_interval_without_key():
    decision = should_refresh(
        NOW,
        NOW - timedelta(days=90),
        interval_days=90,
        key_present=False,
    )

    assert decision.action == "stale"
    assert "compliance data stale" in decision.reason


def test_force_with_key_bypasses_gate():
    decision = should_refresh(
        NOW,
        NOW - timedelta(days=1),
        interval_days=90,
        force=True,
        key_present=True,
    )

    assert decision.action == "refresh"
    assert "force" in decision.reason


def test_missing_timestamp_is_due():
    assert should_refresh(NOW, None, key_present=True).action == "refresh"
    assert should_refresh(NOW, None, key_present=False).action == "stale"


def test_same_elapsed_input_is_deterministic():
    kwargs = {
        "now": NOW,
        "last_success_at": NOW - timedelta(days=42),
        "interval_days": 90,
        "force": False,
        "key_present": True,
    }

    assert should_refresh(**kwargs) == should_refresh(**kwargs)


def test_simulated_year_refreshes_about_quarterly():
    last_success = datetime(2026, 1, 1, tzinfo=timezone.utc)
    refreshes = 0
    for day in range(1, 366):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=day)
        decision = should_refresh(now, last_success, interval_days=90, key_present=True)
        if decision.action == "refresh":
            refreshes += 1
            last_success = now

    assert refreshes <= 4


def test_freshness_status_fresh_due_soon_and_stale_boundaries():
    # Well inside the window -> fresh.
    fresh = freshness_status(NOW, NOW - timedelta(days=40), interval_days=90, warn_within_days=14)
    assert fresh.status == "fresh"

    # Within the warning window of the deadline -> due_soon.
    due = freshness_status(NOW, NOW - timedelta(days=80), interval_days=90, warn_within_days=14)
    assert due.status == "due_soon"
    assert due.days_remaining == pytest.approx(10.0)

    # Past the deadline -> stale.
    stale = freshness_status(NOW, NOW - timedelta(days=95), interval_days=90, warn_within_days=14)
    assert stale.status == "stale"

    # No timestamp at all -> stale.
    assert freshness_status(NOW, None).status == "stale"


def test_freshness_status_is_deterministic():
    kwargs = {"now": NOW, "source_as_of": NOW - timedelta(days=85), "interval_days": 90}
    assert freshness_status(**kwargs) == freshness_status(**kwargs)


def test_bulk_screen_stale_without_key_reuses_cache_and_records_warning(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.json"
    db = tmp_path / "catalog.db"
    cache = tmp_path / "cache"
    manifest.write_text(
        """
        {"sources":{"halal_terminal":{
          "source_as_of":"2026-03-01T00:00:00Z",
          "refresh_interval_days":90,
          "last_row_count":3
        }}}
        """,
        encoding="utf-8",
    )
    monkeypatch.delenv("HALAL_TERMINAL_API_KEY", raising=False)

    def screen_should_not_run(symbol):
        raise AssertionError("stale cadence must not call the screen function")

    stats = bulk_screen_universe(
        ["AAPL", "MSFT"],
        db_path=db,
        manifest_path=manifest,
        cache_dir=cache,
        rate_limit_sleep=0,
        screen_fn=screen_should_not_run,
        now=NOW,
        key_present=False,
    )

    assert stats["screened"] == 0
    assert stats["stale"] == 1
    assert "compliance data stale" in stats["reason"]
    meta = load_manifest(manifest)["sources"][HALAL_TERMINAL_SOURCE_NAME]
    assert meta["refresh_interval_days"] == 90
    assert meta["is_stale"] is True
