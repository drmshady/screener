from __future__ import annotations

import json
from pathlib import Path

from tools.compare_methods import build_report, dumps_report, write_report


def test_compare_methods_regenerates_byte_identically(tmp_path: Path) -> None:
    first = dumps_report(build_report("frozen-sample"))
    second = dumps_report(build_report("frozen-sample"))

    assert first == second

    out = write_report(build_report("frozen-sample"), tmp_path / "report.json")
    assert out.read_text(encoding="utf-8") == first


def test_compare_methods_includes_backtest_delta_and_selected_defaults() -> None:
    report = build_report("frozen-sample")

    assert report["backtest_baseline_delta"]["candidate_exit_model"] == "modeled_levels"
    assert "delta_total_return" in report["backtest_baseline_delta"]
    assert report["selected_default"]["sizing_conviction_signal"] == "none"
    assert report["shipped_defaults_match_selected"] is True


def test_compare_methods_flags_shipped_default_divergence(monkeypatch) -> None:
    monkeypatch.setenv("SCREENER_RISK_DISTANCE_ATR_LO", "9.0")

    report = build_report("frozen-sample")

    assert report["shipped_defaults_match_selected"] is False
    assert report["default_divergences"]["risk_distance_atr_lo"]["shipped"] == 9.0


def test_backtest_delta_is_computed_not_constant() -> None:
    """The delta is produced by the real runner exit functions over the offline
    fixture, not the old hardcoded 0.12/0.09 constants, and stays improvement=False
    (consistent with the gated T038 decision); the offline run is never
    re-baseline-eligible."""
    delta = build_report("frozen-sample")["backtest_baseline_delta"]

    assert delta["basis"] == "synthetic_fixture_mechanics_check"
    assert delta["candidates_evaluated"] == 3
    assert delta["improvement"] is False
    assert delta["rebaseline_eligible"] is False
    # Computed from the fixture, not the retired constants.
    assert (delta["fixed_total_return"], delta["modeled_total_return"]) != (0.12, 0.09)


def test_monotonicity_and_head_to_head_are_computed() -> None:
    sizing = build_report("frozen-sample")["sizing_metrics"]

    mono = sizing["wider_stop_smaller_monotonicity"]
    assert isinstance(mono, dict)
    assert mono["status"] == "pass"
    assert mono["violations"] == 0

    h2h = sizing["conviction_head_to_head"]
    assert set(h2h) == {"none", "fair_value", "inverse_vol", "strategy_rank"}
    assert h2h["none"]["modulated"] == 0
    # Fair value only modulates the trusted-with-positive-margin candidate.
    assert h2h["fair_value"]["modulated"] == 1


def test_real_forward_bars_flip_basis_to_real(tmp_path: Path) -> None:
    snapshot = tmp_path / "real.json"
    snapshot.write_text(
        json.dumps(
            [
                {
                    "ticker": "ZZZ",
                    "entry": 100.0,
                    "stop_loss": 95.0,
                    "take_profit": 110.0,
                    "atr": 2.0,
                    "fair_value": None,
                    "fair_value_trust_flag": "unavailable",
                    "suggested_shares": 100,
                    "cap_bound": False,
                    "as_of": "2026-01-31",
                    "horizon_days": 10,
                    "forward_bars": [
                        {"as_of_date": "2026-02-02", "open": 100, "high": 112, "low": 99, "close": 111},
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    delta = build_report(str(snapshot))["backtest_baseline_delta"]

    assert delta["basis"] == "real_bars"
    assert delta["candidates_evaluated"] == 1
