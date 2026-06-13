import json

from backend.src.data.shariah_halal_terminal import bulk_screen_universe
from backend.src.data.shariah_sources import load_source_rows


def _fake_screen(symbol):
    # AAPL compliant, XOM non-compliant, BABA compliant (no asset_type -> accepted)
    table = {
        "AAPL": {"symbol": "AAPL", "is_compliant": True, "asset_type": "equity", "country": "United States"},
        "XOM": {"symbol": "XOM", "is_compliant": False, "asset_type": "equity", "country": "United States"},
        "BABA": {"symbol": "BABA", "is_compliant": True},
    }
    return table[symbol]


def test_bulk_screen_caches_and_records_compliant(tmp_path):
    db = tmp_path / "catalog.db"
    manifest = tmp_path / "manifest.json"
    cache = tmp_path / "cache"

    stats = bulk_screen_universe(
        ["AAPL", "XOM", "BABA"],
        db_path=db,
        manifest_path=manifest,
        cache_dir=cache,
        rate_limit_sleep=0,
        screen_fn=_fake_screen,
    )

    assert stats["universe"] == 3
    assert stats["screened"] == 3
    assert stats["compliant"] == 2  # AAPL + BABA; XOM excluded (non-compliant)
    rows = load_source_rows(["halal_terminal"], db_path=db)
    assert set(rows.keys()) == {"AAPL", "BABA"}
    # every screened symbol cached (incl. the non-compliant one)
    assert {p.stem for p in cache.glob("*.json")} == {"AAPL", "XOM", "BABA"}


def test_bulk_screen_resumes_from_cache(tmp_path):
    db = tmp_path / "catalog.db"
    manifest = tmp_path / "manifest.json"
    cache = tmp_path / "cache"
    cache.mkdir()
    # Pre-seed cache for AAPL so it is NOT re-screened.
    (cache / "AAPL.json").write_text(json.dumps({"symbol": "AAPL", "is_compliant": True}), encoding="utf-8")

    calls = []

    def screen(symbol):
        calls.append(symbol)
        return {"symbol": symbol, "is_compliant": True}

    stats = bulk_screen_universe(
        ["AAPL", "BABA"], db_path=db, manifest_path=manifest, cache_dir=cache,
        rate_limit_sleep=0, screen_fn=screen,
    )

    assert calls == ["BABA"]  # AAPL served from cache, not re-screened
    assert stats["from_cache"] == 1
    assert stats["screened"] == 1
    assert stats["compliant"] == 2
