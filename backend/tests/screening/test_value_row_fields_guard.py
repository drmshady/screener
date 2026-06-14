"""Engine value-row sanity backstop (RTX corrupted-ratio regression).

A corrupted (stale / wrong-unit) share count makes every yield blow up at once
because they share the market_cap denominator. The backstop must drop all value
yields so such a name can never top-rank on bad data, while keeping the
market-cap-independent F-Score.
"""
from backend.src.screening.engine import _value_row_fields


def _vm(**over):
    base = dict(
        common_equity=59_798_000_000.0, net_income=3_195_000_000.0,
        operating_cf=7_336_000_000.0, revenue=68_920_000_000.0,
        total_assets=161_869_000_000.0, gross_profit=2_153_000_000.0,
        current_assets=48_417_000_000.0, current_liabilities=46_761_000_000.0,
        long_term_debt=43_638_000_000.0, shares_outstanding=1_340_000_000.0,
    )
    base.update(over)
    return base


def test_realistic_shares_produce_sane_yields():
    # ~1.34B shares at $100 -> ~$134B market cap -> sane book/market ~0.45.
    f = _value_row_fields({"value_metrics": _vm()}, 100.0)
    assert f["market_cap"] is not None
    assert 0.0 < f["book_to_market"] < 5.0
    assert abs(f["earnings_yield"]) < 0.5


def test_corrupted_tiny_share_count_drops_all_yields():
    # The RTX bug: 1000x-too-small share count -> book/market ~257, yields ~26x.
    f = _value_row_fields({"value_metrics": _vm(shares_outstanding=1_381_700.0)}, 100.0)
    assert f["market_cap"] is None
    assert f["book_to_market"] is None
    assert f["earnings_yield"] is None
    assert f["cashflow_yield"] is None
    assert f["sales_yield"] is None
    # F-Score is independent of market cap and is still reported.
    assert f["f_score"] is not None


def test_missing_shares_yields_none_not_error():
    f = _value_row_fields({"value_metrics": _vm(shares_outstanding=None)}, 100.0)
    assert f["market_cap"] is None
    assert f["book_to_market"] is None
