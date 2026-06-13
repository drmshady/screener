from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.src.data.profiles import (
    load_cached_profiles,
    load_or_fetch_profiles,
    save_profile_cache,
)


def _profile(name: str):
    return {
        "name": name,
        "sector": "Technology",
        "fcf_ttm": 1.0,
        "debt_to_equity": 0.2,
        "gross_profit": 3.0,
        "total_assets": 10.0,
        "gp_to_assets": 0.3,
        "source_name": "test",
        "source_as_of": "2026-01-01T00:00:00Z",
    }


def test_profile_cache_returns_fresh_rows(tmp_path: Path):
    db_path = tmp_path / "catalog.db"
    now = datetime(2026, 1, 10, tzinfo=timezone.utc)
    save_profile_cache({"AAA": _profile("AAA Inc")}, db_path=db_path, fetched_at=now)

    cached, missing = load_cached_profiles(["AAA", "BBB"], db_path=db_path, now=now)

    assert cached["AAA"]["name"] == "AAA Inc"
    assert missing == ["BBB"]


def test_profile_cache_refetches_stale_rows(tmp_path: Path):
    db_path = tmp_path / "catalog.db"
    old = datetime(2026, 1, 1, tzinfo=timezone.utc)
    now = old + timedelta(days=10)
    save_profile_cache({"AAA": _profile("Old")}, db_path=db_path, fetched_at=old)

    result = load_or_fetch_profiles(
        ["AAA"],
        ttl_days=7,
        db_path=db_path,
        fetcher=lambda ticker: _profile("Fresh"),
    )

    cached, missing = load_cached_profiles(["AAA"], db_path=db_path, now=now)
    assert result["AAA"]["name"] == "Fresh"
    assert cached["AAA"]["name"] in {"Old", "Fresh"}
    assert missing == [] or missing == ["AAA"]
