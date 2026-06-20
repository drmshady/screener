from __future__ import annotations

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
