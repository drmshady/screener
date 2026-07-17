"""Feature 018 T023 (US2) — market-context assemble.

The regime + market-events summary carries a concrete verdict, source, and as-of
(US2 AC3) and is never a bare "Unknown".
"""
from __future__ import annotations

from types import SimpleNamespace

from backend.src.brief import assemble
from backend.src.regime import calculator as regime_calc
from backend.src.events import service as events_service


def _fake_regime(**kwargs):
    return SimpleNamespace(
        regime="Trending up",
        rule_summary="Trending up: SPY is above its 200-day SMA; breadth 65%.",
        inputs=SimpleNamespace(price_source_name="daily-baked SPY"),
        as_of_date="2026-07-08",
    )


class _FakeEvents:
    def market_response(self, *, days_ahead=7):
        return SimpleNamespace(
            events=[SimpleNamespace(event_type="FOMC", event_date="2026-07-15")],
            source_name="curated econ calendar",
            source_as_of="2026-07-07",
        )


def test_market_context_has_concrete_verdict(monkeypatch) -> None:
    monkeypatch.setattr(regime_calc, "current_regime_response", _fake_regime)
    monkeypatch.setattr(events_service, "EventsService", _FakeEvents)

    line = assemble.build_market_context("2026-07-08")
    assert line is not None
    assert line.regime == "Trending up"
    assert "Unknown" not in line.regime
    assert "daily-baked SPY" in line.source
    assert "curated econ calendar" in line.source
    assert line.as_of == "2026-07-08"
    assert line.market_events == ["FOMC on 2026-07-15"]


def test_market_context_fail_soft_on_regime_error(monkeypatch) -> None:
    def _boom(**kwargs):
        raise RuntimeError("spy unavailable")

    monkeypatch.setattr(regime_calc, "current_regime_response", _boom)
    assert assemble.build_market_context("2026-07-08") is None
