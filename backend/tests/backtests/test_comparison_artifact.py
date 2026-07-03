from __future__ import annotations

import json

from backend.src.backtests.runner import build_exit_comparison_artifact


def _result(exit_model: str, total_return: float, max_drawdown: float) -> dict:
    return {
        "id": f"midterm_52w_high_momentum_stooq_2008-01-01_2024-12-31_{exit_model}",
        "strategy_slug": "midterm_52w_high_momentum",
        "computed_at": "2024-12-31T00:00:00Z",
        "summary_metrics": {
            "total_return": total_return,
            "hit_rate": 0.55,
            "avg_win": 0.12,
            "avg_loss": 0.04,
            "max_drawdown": max_drawdown,
            "turnover": 42.0,
        },
    }


def test_comparison_artifact_contains_variants_verdict_and_is_deterministic() -> None:
    first = build_exit_comparison_artifact(
        "midterm_52w_high_momentum",
        _result("fixed_horizon", 0.20, 0.18),
        _result("modeled_levels", 0.24, 0.16),
    )
    second = build_exit_comparison_artifact(
        "midterm_52w_high_momentum",
        _result("fixed_horizon", 0.20, 0.18),
        _result("modeled_levels", 0.24, 0.16),
    )

    assert set(first["variants"]) == {"fixed_horizon", "modeled_levels"}
    assert first["variants"]["fixed_horizon"] == {
        "total_return": 0.20,
        "hit_rate": 0.55,
        "avg_win": 0.12,
        "avg_loss": 0.04,
        "max_drawdown": 0.18,
        "trade_count": 42,
    }
    assert first["variants"]["modeled_levels"]["total_return"] == 0.24
    assert first["verdict"] == "adopt_modeled"
    assert "modeled" in first["decision_note"].lower()
    assert first["snapshot_id"]
    assert first["computed_at"] == "2024-12-31T00:00:00Z"
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_regime_overlay_adopted_only_on_documented_drawdown_improvement() -> None:
    # Overlay lowers drawdown (0.12 < 0.18) without reducing total return
    # (0.20 == 0.20) -> adopt (US5, FR-006).
    artifact = build_exit_comparison_artifact(
        "midterm_52w_high_momentum",
        _result("fixed_horizon", 0.20, 0.18),
        _result("modeled_levels", 0.24, 0.16),
        regime_overlay=_result("regime_overlay", 0.20, 0.12),
    )

    assert set(artifact["variants"]) == {
        "fixed_horizon",
        "modeled_levels",
        "regime_overlay",
    }
    assert artifact["variants"]["regime_overlay"]["max_drawdown"] == 0.12
    assert artifact["verdict"] == "adopt_regime_overlay"
    assert "drawdown" in artifact["decision_note"].lower()


def test_regime_overlay_kept_baseline_when_no_drawdown_improvement() -> None:
    # Overlay does not reduce drawdown vs the overlay-OFF baseline -> keep baseline,
    # never a silent adoption (FR-006, "test, don't trust").
    artifact = build_exit_comparison_artifact(
        "midterm_52w_high_momentum",
        _result("fixed_horizon", 0.20, 0.18),
        _result("modeled_levels", 0.24, 0.16),
        regime_overlay=_result("regime_overlay", 0.15, 0.19),
    )

    assert artifact["verdict"] == "keep_baseline"
    assert "regime_overlay" in artifact["variants"]


def test_regime_overlay_kept_when_drawdown_gain_costs_total_return() -> None:
    # Lower drawdown but at the cost of total return -> not adopted (must not give
    # up return for the drawdown gain).
    artifact = build_exit_comparison_artifact(
        "midterm_52w_high_momentum",
        _result("fixed_horizon", 0.20, 0.18),
        _result("modeled_levels", 0.24, 0.16),
        regime_overlay=_result("regime_overlay", 0.10, 0.05),
    )

    assert artifact["verdict"] == "keep_baseline"
