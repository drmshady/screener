"""T132a: the live halal screen overlays fresh warm-store (yfinance) bars on the
static Stooq deep history without per-run network calls."""
from __future__ import annotations

from datetime import date

import pandas as pd

from backend.src.screening import engine


def _stooq_frame() -> pd.DataFrame:
    # Stooq deep history ending 2026-06-08 (static archive — goes stale).
    rows = []
    for d in pd.bdate_range("2026-05-01", "2026-06-08"):
        rows.append(
            {"ticker": "AAA", "as_of_date": d, "open": 10.0, "high": 10.5,
             "low": 9.5, "close": 10.0, "volume": 1_000_000}
        )
    return pd.DataFrame(rows)


def test_overlay_extends_history_with_fresh_bars(monkeypatch):
    stooq = _stooq_frame()
    # Warm store carries two newer bars (2026-06-09, 2026-06-10) the archive lacks.
    fresh = pd.DataFrame(
        [
            {"ticker": "AAA", "as_of_date": pd.Timestamp("2026-06-09"), "open": 11.0,
             "high": 11.2, "low": 10.8, "close": 11.0, "volume": 2_000_000},
            {"ticker": "AAA", "as_of_date": pd.Timestamp("2026-06-10"), "open": 12.0,
             "high": 12.3, "low": 11.7, "close": 12.0, "volume": 2_500_000},
        ]
    )
    monkeypatch.setattr(engine, "load_prices", lambda *a, **k: fresh)

    merged = engine._overlay_fresh_prices(stooq, ["AAA"], date(2026, 6, 11))
    assert merged["as_of_date"].max() == pd.Timestamp("2026-06-10")
    # The fresh last close is now present (archive ended at 10.0 on 06-08).
    last = merged.sort_values("as_of_date").iloc[-1]
    assert last["close"] == 12.0


def test_overlay_yfinance_wins_on_overlap(monkeypatch):
    stooq = _stooq_frame()
    # A corrected 2026-06-08 close from the warm store must override Stooq's.
    fresh = pd.DataFrame(
        [
            {"ticker": "AAA", "as_of_date": pd.Timestamp("2026-06-08"), "open": 10.0,
             "high": 10.5, "low": 9.5, "close": 99.0, "volume": 1_000_000},
        ]
    )
    monkeypatch.setattr(engine, "load_prices", lambda *a, **k: fresh)

    merged = engine._overlay_fresh_prices(stooq, ["AAA"], date(2026, 6, 11))
    row = merged[merged["as_of_date"] == pd.Timestamp("2026-06-08")]
    assert len(row) == 1  # no duplicate (ticker, date)
    assert row.iloc[0]["close"] == 99.0  # overlay wins


def test_overlay_noop_when_store_empty(monkeypatch):
    stooq = _stooq_frame()
    monkeypatch.setattr(engine, "load_prices", lambda *a, **k: pd.DataFrame())
    merged = engine._overlay_fresh_prices(stooq, ["AAA"], date(2026, 6, 11))
    assert len(merged) == len(stooq)
    assert merged["as_of_date"].max() == pd.Timestamp("2026-06-08")


def test_overlay_resilient_to_store_error(monkeypatch):
    stooq = _stooq_frame()

    def _boom(*a, **k):
        raise RuntimeError("store unavailable")

    monkeypatch.setattr(engine, "load_prices", _boom)
    merged = engine._overlay_fresh_prices(stooq, ["AAA"], date(2026, 6, 11))
    # Fails open to Stooq-only rather than breaking the screen.
    assert merged["as_of_date"].max() == pd.Timestamp("2026-06-08")
