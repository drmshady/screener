from __future__ import annotations

from decimal import Decimal

import pytest

from backend.src.agent.advisor_prompt import (
    build_holding_advisor_prompt,
    build_portfolio_advisor_prompt,
)
from backend.src.models.portfolio import (
    HoldingLevels,
    HoldingRisk,
    LevelBlock,
    PortfolioHolding,
    PortfolioTotals,
)

FAIL_SURV = {
    "confirmed": True,
    "passed": False,
    "note": "no delisted tickers in the free bundle",
}
DISCLAIMER = (
    "This product is for informational purposes only and does not constitute "
    "financial advice. It does not place trades."
)


def _level_block(*, status: str = "holding") -> LevelBlock:
    return LevelBlock(
        entry=Decimal("100.00"),
        stop_loss=Decimal("90.00"),
        tighter_stop_loss=Decimal("95.00"),
        take_profit=Decimal("130.00"),
        risk_distance=Decimal("10.00"),
        reward_distance=Decimal("30.00"),
        reward_ceiling_basis="3R",
        bounds_applied=["risk_floor"],
        levels_state="ok",
        rationale="Bounded levels derived from ATR and horizon.",
        distance_to_stop_pct=-0.18,
        distance_to_target_pct=0.18,
        status=status,
    )


def _holding(ticker: str = "AAA", *, priceable: bool = True) -> PortfolioHolding:
    base = dict(
        ticker=ticker,
        net_quantity=Decimal("50"),
        avg_cost=Decimal("100.00"),
        cost_basis=Decimal("5000.00"),
        earliest_buy_date="2025-07-28",
        most_recent_buy_date="2025-10-09",
        realized_pl=Decimal("0.00"),
        status="open",
    )
    if not priceable:
        return PortfolioHolding(
            **base,
            priceable=False,
            sector="Unclassified",
            data_notes=["no OHLCV data for this ticker on the current snapshot"],
        )
    return PortfolioHolding(
        **base,
        priceable=True,
        sector="Technology",
        current_price=Decimal("110.00"),
        unrealized_pl=Decimal("500.00"),
        unrealized_pl_pct=0.10,
        data_notes=[],
        data_as_of="2026-06-12T00:00:00Z",
        levels=HoldingLevels(
            original_plan=_level_block(),
            current_condition=_level_block(),
        ),
        risk=HoldingRisk(
            recommended_shares=40,
            recommended_value=Decimal("4400.00"),
            actual_shares=Decimal("50"),
            actual_value=Decimal("5500.00"),
            actual_capital_at_risk=Decimal("500.00"),
            actual_capital_at_risk_pct=0.05,
            per_trade_risk_budget=Decimal("100.00"),
            over_risk=True,
            binding_constraint="per_trade_budget",
            sizing_reasoning="Risk-per-trade target binds before the position cap.",
            fail_open=False,
        ),
    )


# --- single-holding prompt ------------------------------------------------


def test_holding_prompt_contains_facts_levels_risk(midterm_strategy):
    prompt = build_holding_advisor_prompt(
        _holding(),
        midterm_strategy,
        survivorship=FAIL_SURV,
        regime="Trending up",
    )
    # held-position framing + facts
    assert "AAA" in prompt
    assert "Average cost" in prompt
    assert "Net quantity" in prompt
    assert "Unrealized" in prompt
    # both purchase-anchored level bases, labelled
    assert "Original-plan" in prompt
    assert "Current-condition" in prompt
    # risk view
    assert "Suggested" in prompt and "actual" in prompt.lower()
    assert "Capital at risk" in prompt
    assert "per_trade_budget" in prompt
    # strategy context + regime + honesty
    assert midterm_strategy.citation in prompt
    assert "Trending up" in prompt
    assert "survivorship" in prompt.lower() and "optimistic" in prompt.lower()
    assert DISCLAIMER in prompt
    # honesty block is present and is the last section
    assert "## Honesty" in prompt
    sections = [s for s in prompt.split("\n## ")]
    assert sections[-1].startswith("Honesty")


def test_holding_prompt_is_deterministic(midterm_strategy):
    a = build_holding_advisor_prompt(
        _holding(), midterm_strategy, survivorship=FAIL_SURV, regime="Trending up"
    )
    b = build_holding_advisor_prompt(
        _holding(), midterm_strategy, survivorship=FAIL_SURV, regime="Trending up"
    )
    assert a == b
    assert "T00:00:00Z" not in a  # no full-ISO wall-clock leaks into the body


def test_holding_prompt_neutral_has_no_directive_language(midterm_strategy):
    prompt = build_holding_advisor_prompt(
        _holding(),
        midterm_strategy,
        survivorship=FAIL_SURV,
        regime="Trending up",
        directive=False,
    )
    lower = prompt.lower()
    for word in ("buy", "sell", "recommended", "strong buy"):
        assert word not in lower


def test_holding_prompt_directive_adds_take_trim_exit(midterm_strategy):
    prompt = build_holding_advisor_prompt(
        _holding(),
        midterm_strategy,
        survivorship=FAIL_SURV,
        regime="Trending up",
        directive=True,
    )
    lower = prompt.lower()
    assert "trim" in lower and "exit" in lower
    assert "single owner" in lower  # personal-use scope line


def test_holding_prompt_out_of_coverage_is_facts_only(midterm_strategy):
    prompt = build_holding_advisor_prompt(
        _holding(priceable=False),
        midterm_strategy,
        survivorship=FAIL_SURV,
        regime=None,
    )
    assert "AAA" in prompt
    assert "not priceable" in prompt.lower()
    # still a valid prompt with the honesty block
    assert DISCLAIMER in prompt


# --- whole-portfolio prompt ----------------------------------------------


def test_portfolio_prompt_covers_all_holdings(midterm_strategy):
    totals = PortfolioTotals(
        total_invested=Decimal("11000.00"),
        total_capital_at_risk=Decimal("900.00"),
        total_capital_at_risk_pct=0.045,
    )
    prompt = build_portfolio_advisor_prompt(
        [_holding("AAA"), _holding("BBB")],
        totals,
        midterm_strategy,
        survivorship=FAIL_SURV,
        regime="Trending up",
    )
    assert "AAA" in prompt and "BBB" in prompt
    assert "Holdings (2)" in prompt
    # totals line
    assert "Total invested" in prompt
    assert "Total capital at risk" in prompt
    # strategy context + citation appear once
    assert prompt.count(midterm_strategy.citation) == 1
    # honesty once
    assert prompt.lower().count("survivorship bias") <= 2  # caveat + maybe label


def test_portfolio_prompt_is_deterministic(midterm_strategy):
    totals = PortfolioTotals(
        total_invested=Decimal("11000.00"),
        total_capital_at_risk=Decimal("900.00"),
        total_capital_at_risk_pct=0.045,
    )
    a = build_portfolio_advisor_prompt(
        [_holding("AAA"), _holding("BBB")], totals, midterm_strategy, survivorship=FAIL_SURV
    )
    b = build_portfolio_advisor_prompt(
        [_holding("AAA"), _holding("BBB")], totals, midterm_strategy, survivorship=FAIL_SURV
    )
    assert a == b


def test_portfolio_prompt_neutral_has_no_directive_language(midterm_strategy):
    totals = PortfolioTotals(total_invested=Decimal("0.00"))
    prompt = build_portfolio_advisor_prompt(
        [_holding("AAA")], totals, midterm_strategy, survivorship=FAIL_SURV, directive=False
    )
    lower = prompt.lower()
    for word in ("buy", "sell", "recommended", "strong buy"):
        assert word not in lower


def test_portfolio_prompt_handles_empty(midterm_strategy):
    totals = PortfolioTotals(total_invested=Decimal("0.00"))
    prompt = build_portfolio_advisor_prompt(
        [], totals, midterm_strategy, survivorship=FAIL_SURV
    )
    assert "Holdings (0)" in prompt
    assert DISCLAIMER in prompt
