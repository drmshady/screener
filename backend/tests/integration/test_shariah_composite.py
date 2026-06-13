from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from backend.src.data.shariah_sources import replace_source_rows
from backend.src.shariah.lookup import ShariahLookup


def _paths(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "catalog.db", tmp_path / "manifest.json"


def test_composite_lookup_source_precedence_and_conflicts(tmp_path: Path) -> None:
    db_path, manifest_path = _paths(tmp_path)
    replace_source_rows(
        "spus_holdings",
        [
            {
                "ticker": "AAPL",
                "source_as_of": "2026-06-10T00:00:00Z",
                "source_url": "https://example.test/spus.csv",
            },
            {
                "ticker": "MSFT",
                "source_as_of": "2026-06-10T00:00:00Z",
                "source_url": "https://example.test/spus.csv",
            },
        ],
        db_path=db_path,
        manifest_path=manifest_path,
    )

    lookup = ShariahLookup(
        {
            "active_sources": ["spus_holdings"],
            "inclusion": [
                {"ticker": "TSLA", "direction": "include", "note": "Personal review"},
                {"ticker": "AAPL", "direction": "include", "note": "Keep note"},
                {"ticker": "MSFT", "direction": "include", "note": "Conflict note"},
            ],
            "exclusion": [
                {"ticker": "MSFT", "direction": "exclude", "note": "Excluded source"},
                {"ticker": "TSLA", "direction": "exclude", "note": "Conflict wins"},
            ],
        },
        db_path=db_path,
        manifest_path=manifest_path,
    )

    aapl = lookup.status("AAPL")
    assert aapl.is_compliant is True
    assert aapl.source_kind == "external"
    assert aapl.external_source_name == "spus_holdings"
    assert aapl.user_note == "Keep note"

    tsla = lookup.status("TSLA")
    assert tsla.is_compliant is False
    assert tsla.source_kind == "excluded_by_user"
    assert tsla.conflict is True
    assert tsla.user_note == "Conflict wins"

    msft = lookup.status("MSFT")
    assert msft.is_compliant is False
    assert msft.source_kind == "excluded_by_user"
    assert msft.external_source_name == "spus_holdings"
    assert msft.conflict is True

    nvda = lookup.status("NVDA")
    assert nvda.is_compliant is False
    assert nvda.source_kind == "not_listed"


def test_user_inclusion_only_is_compliant(tmp_path: Path) -> None:
    db_path, manifest_path = _paths(tmp_path)
    manifest_path.write_text(json.dumps({"sources": {}}), encoding="utf-8")
    lookup = ShariahLookup(
        {
            "active_sources": [],
            "inclusion": [
                {"ticker": "UNH", "direction": "include", "note": "Manual screen"}
            ],
            "exclusion": [],
        },
        db_path=db_path,
        manifest_path=manifest_path,
    )

    status = lookup.status("UNH")
    assert status.is_compliant is True
    assert status.source_kind == "user"
    assert status.user_note == "Manual screen"


def test_filter_off_does_not_construct_shariah_lookup(monkeypatch) -> None:
    from backend.src.screening import engine

    def rules(_universe: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "ticker": "AAPL",
                    "name": "Apple Inc.",
                    "sector": "Technology",
                    "close": 200.0,
                    "entry": 201.0,
                    "stop_loss": 190.0,
                    "take_profit": 225.0,
                    "score": 1.0,
                    "reason": "Fixture match",
                }
            ]
        )

    fake_strategy = SimpleNamespace(
        slug="fake_strategy",
        name="Fake Strategy",
        timeframe="Mid-term",
        default_exclude_earnings_within_days=0,
        rules=rules,
    )

    monkeypatch.setattr(
        engine.registry,
        "get",
        lambda slug: fake_strategy if slug == "fake_strategy" else None,
    )
    monkeypatch.setattr(
        engine,
        "build_universe_snapshot",
        lambda *args, **kwargs: (
            pd.DataFrame([{"ticker": "AAPL"}]),
            "2026-06-10T21:00:00Z",
        ),
    )

    class RaisingLookup:
        def __init__(self, *args, **kwargs):  # pragma: no cover - should never run
            raise AssertionError(
                "ShariahLookup should not be constructed when filter is off"
            )

    monkeypatch.setattr(engine, "ShariahLookup", RaisingLookup)

    result = engine.run_strategy(
        "fake_strategy",
        parameters={"tickers": ["AAPL"]},
        filters={"shariah_only": False},
        shariah_overrides={"inclusion": [{"ticker": "AAPL", "direction": "include"}]},
    )

    assert result.candidate_count == 1
    assert result.candidates[0].shariah_compliant is None
