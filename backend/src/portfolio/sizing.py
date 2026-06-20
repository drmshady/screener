from __future__ import annotations

from decimal import Decimal, ROUND_FLOOR

from ..lib import flags
from ..models.portfolio import SizingRequest, SizingResponse, money, pct
from .exposure import aggregate_exposure, holding_value

# Conviction-scale clamp band shared by every candidate modulator (Decision 3) —
# placeholder pending US4 calibration (research.md Decision 6).
_CONVICTION_BOOST_CAP = 1.5
_CONVICTION_SHRINK_FLOOR = 0.5


def _cap_amount(total_capital: Decimal, cap_pct: float) -> Decimal:
    return money(total_capital * Decimal(str(cap_pct)))


def _floor_shares(value: Decimal) -> int:
    if value <= 0:
        return 0
    return int(value.to_integral_value(rounding=ROUND_FLOOR))


def _legacy_cap_fill(request: SizingRequest) -> SizingResponse:
    """Pre-US3 behavior: fill the lower remaining cap room, no risk/conviction
    awareness. Kept for callers that don't supply a stop_loss (backward
    compatible — contracts/sizing.md does not require a stop)."""
    exposure = aggregate_exposure(
        request.holdings, total_capital=request.total_capital, caps=request.caps
    )
    candidate_sector = request.candidate_sector or "Unclassified"
    current_position_value = sum(
        (
            holding_value(holding)
            for holding in request.holdings
            if holding.ticker == request.candidate_ticker
        ),
        Decimal("0"),
    )
    current_sector_value = sum(
        (
            sector.dollar_value
            for sector in exposure.sectors
            if sector.sector == candidate_sector
        ),
        Decimal("0"),
    )

    position_cap = _cap_amount(request.total_capital, request.caps.per_position_cap_pct)
    sector_cap = _cap_amount(request.total_capital, request.caps.per_sector_cap_pct)
    remaining_position_room = position_cap - current_position_value
    remaining_sector_room = sector_cap - current_sector_value
    max_trade_value = min(remaining_position_room, remaining_sector_room)

    if max_trade_value < request.entry:
        one_share_position_pct = pct(
            current_position_value + request.entry, request.total_capital
        )
        one_share_sector_pct = pct(
            current_sector_value + request.entry, request.total_capital
        )
        return SizingResponse(
            suggested_shares=0,
            suggested_position_value=money(Decimal("0")),
            resulting_position_pct_of_capital=one_share_position_pct,
            resulting_sector_pct_of_capital=one_share_sector_pct,
            caps_respected=False,
            reasoning=(
                "Cannot size without breaching cap. One share at "
                f"${money(request.entry)} would put the position at "
                f"{one_share_position_pct:.2%} of capital and {candidate_sector} at "
                f"{one_share_sector_pct:.2%}."
            ),
        )

    shares = _floor_shares(max_trade_value / request.entry)
    trade_value = money(request.entry * Decimal(shares))
    resulting_position_value = current_position_value + trade_value
    resulting_sector_value = current_sector_value + trade_value
    resulting_position_pct = pct(resulting_position_value, request.total_capital)
    resulting_sector_pct = pct(resulting_sector_value, request.total_capital)
    caps_respected = (
        resulting_position_pct <= request.caps.per_position_cap_pct
        and resulting_sector_pct <= request.caps.per_sector_cap_pct
    )

    return SizingResponse(
        suggested_shares=shares,
        suggested_position_value=trade_value,
        resulting_position_pct_of_capital=resulting_position_pct,
        resulting_sector_pct_of_capital=resulting_sector_pct,
        caps_respected=caps_respected,
        reasoning=(
            f"Whole-share size uses the lower remaining room between the "
            f"{request.caps.per_position_cap_pct:.1%} position cap and "
            f"{request.caps.per_sector_cap_pct:.1%} sector cap."
        ),
    )


def _conviction_scale(request: SizingRequest) -> tuple[float, str, str, bool, str]:
    """Returns (scale, signal, adjustment, used, note) for the US4-adopted
    conviction modulator (Decision 3). ``used=False`` (scale=1.0) whenever the
    adopted signal's input is missing/untrusted — fail-open, never an error
    (FR-016)."""
    signal = flags.sizing_conviction_signal()

    if signal == "fair_value":
        if (
            request.fair_value is not None
            and request.fair_value_trust_flag == "trusted"
            and request.fair_value > 0
        ):
            fair_value = float(request.fair_value)
            margin = (fair_value - float(request.entry)) / fair_value
            scale = min(max(1.0 + margin, _CONVICTION_SHRINK_FLOOR), _CONVICTION_BOOST_CAP)
            adjustment = "boost" if scale > 1.0 else ("cap" if scale < 1.0 else "none")
            return scale, signal, adjustment, True, f"fair-value margin of safety {margin:.1%}"
        return 1.0, signal, "none", False, "fair value unavailable/untrusted; risk-based sizing only"

    if signal == "inverse_vol":
        if request.volatility is not None and request.volatility > 0:
            baseline = flags.sizing_inverse_vol_baseline()
            scale = min(
                max(baseline / request.volatility, _CONVICTION_SHRINK_FLOOR),
                _CONVICTION_BOOST_CAP,
            )
            adjustment = "boost" if scale > 1.0 else ("cap" if scale < 1.0 else "none")
            return (
                scale,
                signal,
                adjustment,
                True,
                f"volatility {request.volatility:.4f} vs baseline {baseline:.4f}",
            )
        return 1.0, signal, "none", False, "volatility unavailable; risk-based sizing only"

    if signal == "strategy_rank":
        if request.strategy_rank is not None and request.strategy_rank >= 1:
            scale = min(
                max(1.5 - 0.05 * (request.strategy_rank - 1), _CONVICTION_SHRINK_FLOOR),
                _CONVICTION_BOOST_CAP,
            )
            adjustment = "boost" if scale > 1.0 else ("cap" if scale < 1.0 else "none")
            return scale, signal, adjustment, True, f"strategy rank {request.strategy_rank}"
        return 1.0, signal, "none", False, "strategy rank unavailable; risk-based sizing only"

    return 1.0, "none", "none", False, "risk-per-trade sizing only (no conviction modulation adopted)"


def _risk_based_sizing(request: SizingRequest) -> SizingResponse:
    """Risk-per-trade backbone + the adopted conviction modulation, hard-bounded
    by the existing per-position/per-sector caps (contracts/sizing.md)."""
    exposure = aggregate_exposure(
        request.holdings, total_capital=request.total_capital, caps=request.caps
    )
    candidate_sector = request.candidate_sector or "Unclassified"
    current_position_value = sum(
        (
            holding_value(holding)
            for holding in request.holdings
            if holding.ticker == request.candidate_ticker
        ),
        Decimal("0"),
    )
    current_sector_value = sum(
        (
            sector.dollar_value
            for sector in exposure.sectors
            if sector.sector == candidate_sector
        ),
        Decimal("0"),
    )

    risk_per_share = money(request.entry - request.stop_loss)
    risk_budget = money(request.total_capital * Decimal(str(flags.risk_per_trade_fraction())))
    target_shares = _floor_shares(risk_budget / risk_per_share) if risk_per_share > 0 else 0

    scale, signal, adjustment, used, note = _conviction_scale(request)
    modulated_shares = (
        target_shares
        if scale == 1.0
        else _floor_shares(Decimal(target_shares) * Decimal(str(scale)))
    )

    position_cap = _cap_amount(request.total_capital, request.caps.per_position_cap_pct)
    sector_cap = _cap_amount(request.total_capital, request.caps.per_sector_cap_pct)
    remaining_position_room = position_cap - current_position_value
    remaining_sector_room = sector_cap - current_sector_value
    max_trade_value = min(remaining_position_room, remaining_sector_room)
    max_shares_by_cap = _floor_shares(max_trade_value / request.entry) if max_trade_value > 0 else 0

    if max_shares_by_cap < modulated_shares:
        final_shares = max_shares_by_cap
        binding_constraint = (
            "position_cap" if remaining_position_room <= remaining_sector_room else "sector_cap"
        )
    elif used and scale != 1.0:
        final_shares = modulated_shares
        binding_constraint = "conviction"
    else:
        final_shares = modulated_shares
        binding_constraint = "risk_target"

    trade_value = money(request.entry * Decimal(final_shares))
    resulting_position_value = current_position_value + trade_value
    resulting_sector_value = current_sector_value + trade_value
    resulting_position_pct = pct(resulting_position_value, request.total_capital)
    resulting_sector_pct = pct(resulting_sector_value, request.total_capital)

    reasoning = (
        f"Risk-per-trade target is {target_shares} shares (risking "
        f"{flags.risk_per_trade_fraction():.2%} of capital across the "
        f"${risk_per_share} stop distance)"
    )
    reasoning += f"; conviction signal {signal} used ({note})" if used else f"; {note}"
    reasoning += f". Binding constraint: {binding_constraint.replace('_', ' ')}."

    return SizingResponse(
        suggested_shares=final_shares,
        suggested_position_value=trade_value,
        resulting_position_pct_of_capital=resulting_position_pct,
        resulting_sector_pct_of_capital=resulting_sector_pct,
        caps_respected=True,
        reasoning=reasoning,
        risk_per_trade_target=risk_budget,
        risk_per_share=risk_per_share,
        conviction_signal=signal,
        conviction_adjustment=adjustment,
        binding_constraint=binding_constraint,
        conviction_used=used,
    )


def size_position(request: SizingRequest) -> SizingResponse:
    if (
        request.stop_loss is None
        or request.stop_loss <= 0
        or request.stop_loss >= request.entry
    ):
        return _legacy_cap_fill(request)
    return _risk_based_sizing(request)
