"""T002 / FR-008 / SC-004 — frozen pre-feature baseline of the sentiment-free
prompt blocks.

Feature 017 embeds a sentiment section only for tickers that have a captured
report; every other block must be **byte-identical** to the pre-feature output.
These fixtures freeze that pre-feature output for one screen candidate and one
holding so the byte-identical-absent guarantee is anchored to a concrete
artifact (not only recomputed inline in the per-story tests).

If a legitimate, unrelated builder-copy change lands, regenerate the fixtures
under `fixtures/017_baseline_prompts/` and re-review the diff — it must contain
no sentiment content.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from backend.src.agent.advisor_prompt import _candidate_summary_block, _holding_block
from backend.src.models.portfolio import (
    HoldingLevels,
    HoldingRisk,
    LevelBlock,
    PortfolioHolding,
)
from backend.src.models.strategy import Candidate, GateResult

_FIXTURES = Path(__file__).parent / "fixtures" / "017_baseline_prompts"
_HEADING = "### External context — sentiment & narrative"


def _candidate() -> Candidate:
    return Candidate(
        ticker="FOO",
        name="FOO Inc",
        sector="Technology",
        strategy_slug="midterm_52w_high_momentum",
        current_price="100.00",
        entry="100.00",
        stop_loss="90.00",
        tighter_stop_loss="95.00",
        take_profit="130.00",
        rank=2,
        score=0.5,
        return_12_1=0.4,
        vol_scalar=0.9,
        dist_to_high=0.02,
        atr=3.0,
        reason="matched",
        gate_results=[
            GateResult(gate="52-week-high proximity", status="pass", detail="1% below high"),
        ],
        recent_8k_count_30d=0,
    )


def _level_block() -> LevelBlock:
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
        status="holding",
    )


def _holding() -> PortfolioHolding:
    return PortfolioHolding(
        ticker="FOO",
        net_quantity=Decimal("50"),
        avg_cost=Decimal("100.00"),
        cost_basis=Decimal("5000.00"),
        earliest_buy_date="2025-07-28",
        most_recent_buy_date="2025-10-09",
        realized_pl=Decimal("0.00"),
        status="open",
        priceable=True,
        sector="Technology",
        current_price=Decimal("110.00"),
        unrealized_pl=Decimal("500.00"),
        unrealized_pl_pct=0.10,
        data_notes=[],
        data_as_of="2026-06-12T00:00:00Z",
        levels=HoldingLevels(original_plan=_level_block(), current_condition=_level_block()),
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


def _read(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def test_screen_candidate_block_matches_frozen_baseline():
    block = _candidate_summary_block(
        _candidate(),
        sector_gate_on=False,
        material_freshness=None,
        default_as_of="2026-06-12",
    )
    assert block == _read("screen_candidate_block.md")
    assert _HEADING not in block


def test_holding_block_matches_frozen_baseline():
    block = _holding_block(_holding())
    assert block == _read("holding_block.md")
    assert _HEADING not in block
