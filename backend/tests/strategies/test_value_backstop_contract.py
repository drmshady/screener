"""T010 [US1] — the value strategy's implausibility backstop, re-expressed as an
OutputContract, runs through the SAME engine with no per-strategy engine code
(FR-006 / SC-009), and the value backtest baseline is unchanged (SC-010).

Written FIRST: must FAIL before ``midterm_value_composite.OUTPUT_CONTRACT``
exists (T014).

The existing inline backstop (``engine._value_row_fields``) drops every value
yield when any one blows past its bound because they share the market-cap
denominator. Re-expressed declaratively, the same bounds become value-domain
invariants the strategy-agnostic ``evaluate_contract`` enforces — proving one
engine serves both strategies.
"""
from __future__ import annotations

import pandas as pd

from backend.src.screening.engine import _value_row_fields
from backend.src.screening.integrity.contract import OutputContract
from backend.src.screening.integrity.engine import evaluate_contract
from backend.src.strategies import midterm_value_composite as val


def test_value_strategy_exposes_an_output_contract():
    contract = val.OUTPUT_CONTRACT
    assert isinstance(contract, OutputContract)
    assert contract.strategy_slug == "midterm_value_composite"
    # the backstop bounds are declared as value-domain invariants
    families = {inv.family for inv in contract.invariants}
    assert "value_domain" in families


def test_implausible_yields_are_flagged_by_the_shared_engine():
    # A row carrying the pre-backstop implausible yields (corrupted market cap).
    df = pd.DataFrame(
        [
            {"ticker": "GOODVAL", "book_to_market": 0.9, "earnings_yield": 0.12,
             "cashflow_yield": 0.10, "sales_yield": 2.0},
            {"ticker": "RTXBAD", "book_to_market": 257.0, "earnings_yield": 26.0,
             "cashflow_yield": 26.0, "sales_yield": 80.0},
        ]
    )
    out = evaluate_contract(df, val.OUTPUT_CONTRACT)

    good = out.loc[out["ticker"] == "GOODVAL"].iloc[0]
    assert bool(good["data_suspect"]) is False
    assert list(good["data_integrity_warnings"]) == []

    bad = out.loc[out["ticker"] == "RTXBAD"].iloc[0]
    assert bool(bad["data_suspect"]) is True
    flagged = {w.figure for w in bad["data_integrity_warnings"]}
    # at least the book/market guard fires (the others share the bad denominator)
    assert "book_to_market" in flagged


def test_contract_bounds_match_the_inline_backstop_behaviour():
    """The same corrupted share count that the inline backstop drops (all yields
    nulled) is the case the contract flags — behaviour is consistent (FR-006)."""
    vm = dict(
        common_equity=59_798_000_000.0, net_income=3_195_000_000.0,
        operating_cf=7_336_000_000.0, revenue=68_920_000_000.0,
        total_assets=161_869_000_000.0, gross_profit=2_153_000_000.0,
        current_assets=48_417_000_000.0, current_liabilities=46_761_000_000.0,
        long_term_debt=43_638_000_000.0, shares_outstanding=1_381_700.0,  # 1000x too small
    )
    fields = _value_row_fields({"value_metrics": vm}, 100.0)
    # Inline backstop nulls the yields (baseline behaviour unchanged, SC-010).
    assert fields["book_to_market"] is None

    # The pre-null implausible figures, fed to the contract, are flagged.
    implausible = pd.DataFrame([{ "ticker": "RTX", "book_to_market": 257.0 }])
    out = evaluate_contract(implausible, val.OUTPUT_CONTRACT)
    assert bool(out.iloc[0]["data_suspect"]) is True
