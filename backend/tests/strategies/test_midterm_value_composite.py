"""Rules-level unit tests for midterm_value_composite (Principle IV).

Written before the strategy module; they MUST fail first. Default gate mode is
hard (value-trap names excluded).
"""
import pandas as pd
import pytest

from backend.src.strategies import midterm_value_composite as strat


def _universe() -> pd.DataFrame:
    # All in one sector so within-sector ranking == global ranking for the test.
    rows = [
        # cheap + healthy -> should be selected
        dict(ticker="GOOD", sector="Tech", close=50.0, atr=1.0, sma_200=45.0,
             contraction_low_20=47.0, debt_to_equity=1.0, fcf_ttm=10.0,
             book_to_market=0.9, earnings_yield=0.12, cashflow_yield=0.10, sales_yield=2.0,
             f_score=8, f_score_evaluable=9),
        # cheap but failing F-Score -> value trap, excluded
        dict(ticker="TRAP", sector="Tech", close=30.0, atr=1.0, sma_200=28.0,
             contraction_low_20=29.0, debt_to_equity=1.0, fcf_ttm=5.0,
             book_to_market=1.1, earnings_yield=0.15, cashflow_yield=0.12, sales_yield=2.5,
             f_score=2, f_score_evaluable=9),
        # expensive (low yields) but healthy -> fails composite cut
        dict(ticker="RICH", sector="Tech", close=100.0, atr=1.0, sma_200=90.0,
             contraction_low_20=95.0, debt_to_equity=0.5, fcf_ttm=20.0,
             book_to_market=0.05, earnings_yield=0.01, cashflow_yield=0.01, sales_yield=0.2,
             f_score=9, f_score_evaluable=9),
        # cheap + healthy but over-levered -> fails leverage sanity
        dict(ticker="LEVD", sector="Tech", close=40.0, atr=1.0, sma_200=38.0,
             contraction_low_20=39.0, debt_to_equity=6.0, fcf_ttm=3.0,
             book_to_market=0.8, earnings_yield=0.11, cashflow_yield=0.09, sales_yield=1.8,
             f_score=7, f_score_evaluable=9),
    ]
    return pd.DataFrame(rows)


def test_value_trap_excluded_in_hard_mode():
    out = strat.rules(_universe())
    assert "TRAP" not in set(out["ticker"])  # failed F-Score gate


def test_expensive_name_fails_composite_cut():
    out = strat.rules(_universe())
    assert "RICH" not in set(out["ticker"])


def test_overlevered_name_excluded():
    out = strat.rules(_universe())
    assert "LEVD" not in set(out["ticker"])


def test_good_name_selected_with_levels():
    out = strat.rules(_universe()).set_index("ticker")
    assert "GOOD" in out.index
    row = out.loc["GOOD"]
    assert float(row["entry"]) == pytest.approx(50.0)
    assert float(row["stop_loss"]) < float(row["entry"])
    assert float(row["take_profit"]) > float(row["entry"])
    assert row["value_composite"] == row["value_composite"]  # not NaN
    # gate accounting present
    gates = {g["gate"] for g in row["gate_results"]}
    assert "Piotroski F-Score" in gates
    assert "Value composite" in gates


def test_determinism_same_frame_same_output():
    a = strat.rules(_universe())
    b = strat.rules(_universe())
    cols = ["ticker", "entry", "stop_loss", "take_profit", "score"]
    assert a[cols].reset_index(drop=True).equals(b[cols].reset_index(drop=True))


def test_missing_f_score_reported_skipped():
    df = _universe()
    df.loc[df["ticker"] == "GOOD", ["f_score", "f_score_evaluable"]] = [None, 0]
    out = strat.rules(df)
    # With no evaluable health signals the name cannot be confirmed; it is excluded
    # in hard mode, and the universe-level accounting records the F-Score skip.
    notes = out.attrs.get("gates_skipped", []) + out.attrs.get("gates_applied", [])
    assert any("F-Score" in n or "Piotroski" in n for n in notes)


def test_empty_universe_returns_empty():
    out = strat.rules(pd.DataFrame())
    assert out.empty


def _universe_with_momentum() -> pd.DataFrame:
    df = _universe()
    # GOOD is a falling knife (12-1 momentum -50%); the others are flat-ish.
    df["return_12_1"] = [-0.50, 0.05, 0.10, 0.02]  # GOOD, TRAP, RICH, LEVD
    return df


def test_momentum_floor_disabled_by_default_keeps_falling_knife():
    # Default: pure value, no momentum filter -> GOOD (cheap+healthy) still selected
    # despite its -50% momentum.
    out = strat.rules(_universe_with_momentum())
    assert "GOOD" in set(out["ticker"])


def test_momentum_floor_excludes_falling_knife_when_enabled(monkeypatch):
    monkeypatch.setenv("SCREENER_VALUE_MIN_MOMENTUM", "-0.20")
    out = strat.rules(_universe_with_momentum())
    # GOOD's -50% momentum is below the -20% floor -> excluded as a value trap.
    assert "GOOD" not in set(out["ticker"])
    # The momentum-floor gate is recorded in the honest accounting.
    notes = out.attrs.get("gates_applied", []) + out.attrs.get("gates_skipped", [])
    assert any("momentum" in n.lower() for n in notes)


def test_momentum_floor_per_run_override_via_attrs():
    # The UI toggle threads the floor through the universe frame's attrs (not env).
    df = _universe_with_momentum()
    df.attrs["min_momentum_12_1"] = -0.20
    out = strat.rules(df)
    # GOOD's -50% momentum is below the -20% per-run floor -> excluded.
    assert "GOOD" not in set(out["ticker"])
    notes = out.attrs.get("gates_applied", []) + out.attrs.get("gates_skipped", [])
    assert any("momentum" in n.lower() for n in notes)


def test_momentum_floor_attrs_disabled_keeps_falling_knife():
    # A per-run value of -1.0 (UI toggle OFF) leaves pure value -> falling knife kept.
    df = _universe_with_momentum()
    df.attrs["min_momentum_12_1"] = -1.0
    out = strat.rules(df)
    assert "GOOD" in set(out["ticker"])


def test_missing_momentum_passes_through_when_floor_enabled(monkeypatch):
    monkeypatch.setenv("SCREENER_VALUE_MIN_MOMENTUM", "-0.20")
    df = _universe_with_momentum()
    df.loc[df["ticker"] == "GOOD", "return_12_1"] = None  # unknown momentum
    out = strat.rules(df)
    assert "GOOD" in set(out["ticker"])  # fail-open: missing momentum is not excluded


def test_negative_yields_not_top_ranked():
    df = _universe()
    # Make GOOD's yields negative (loss-making, negative book) -> must rank below RICH-style.
    df.loc[df["ticker"] == "GOOD", ["book_to_market", "earnings_yield", "cashflow_yield", "sales_yield"]] = [-0.5, -0.2, -0.1, -0.3]
    out = strat.rules(df)
    if "GOOD" in set(out["ticker"]):
        out = out.set_index("ticker")
        # If it survives at all, it must not be the cheapest (top) name.
        assert out.loc["GOOD", "value_composite"] < out["value_composite"].max()
