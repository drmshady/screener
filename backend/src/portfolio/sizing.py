from __future__ import annotations

from decimal import Decimal, ROUND_FLOOR

from ..models.portfolio import SizingRequest, SizingResponse, money, pct
from .exposure import aggregate_exposure, holding_value


def _cap_amount(total_capital: Decimal, cap_pct: float) -> Decimal:
    return money(total_capital * Decimal(str(cap_pct)))


def size_position(request: SizingRequest) -> SizingResponse:
    exposure = aggregate_exposure(
        request.holdings,
        total_capital=request.total_capital,
        caps=request.caps,
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

    shares = int(
        (max_trade_value / request.entry).to_integral_value(rounding=ROUND_FLOOR)
    )
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
