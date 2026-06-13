from __future__ import annotations

from decimal import Decimal

from ..models.portfolio import (
    ConcentrationFlag,
    PortfolioCaps,
    PortfolioExposure,
    SectorExposure,
    SizingHolding,
    money,
    pct,
)


def holding_value(holding: SizingHolding) -> Decimal:
    return money(holding.shares * holding.current_price)


def aggregate_exposure(
    holdings: list[SizingHolding],
    total_capital: Decimal,
    caps: PortfolioCaps,
) -> PortfolioExposure:
    sector_values: dict[str, Decimal] = {}
    flags: list[ConcentrationFlag] = []
    total_invested = Decimal("0")

    for holding in holdings:
        value = holding_value(holding)
        total_invested += value
        sector = holding.sector or "Unclassified"
        sector_values[sector] = sector_values.get(sector, Decimal("0")) + value

        position_pct = pct(value, total_capital)
        if position_pct > caps.per_position_cap_pct:
            flags.append(
                ConcentrationFlag(
                    kind="position",
                    label=holding.ticker,
                    percent_of_capital=position_pct,
                    cap_pct=caps.per_position_cap_pct,
                    message=(
                        f"{holding.ticker} is {position_pct:.1%} of capital, "
                        f"above the {caps.per_position_cap_pct:.1%} position cap."
                    ),
                )
            )

    sectors: list[SectorExposure] = []
    for sector, value in sorted(sector_values.items()):
        sector_pct = pct(value, total_capital)
        over_cap = sector_pct > caps.per_sector_cap_pct
        sectors.append(
            SectorExposure(
                sector=sector,
                dollar_value=money(value),
                percent_of_capital=sector_pct,
                cap_pct=caps.per_sector_cap_pct,
                over_cap=over_cap,
            )
        )
        if over_cap:
            flags.append(
                ConcentrationFlag(
                    kind="sector",
                    label=sector,
                    percent_of_capital=sector_pct,
                    cap_pct=caps.per_sector_cap_pct,
                    message=(
                        f"{sector} is {sector_pct:.1%} of capital, "
                        f"above the {caps.per_sector_cap_pct:.1%} sector cap."
                    ),
                )
            )

    return PortfolioExposure(
        total_capital=money(total_capital),
        total_invested=money(total_invested),
        cash_balance=money(total_capital - total_invested),
        sectors=sectors,
        concentration_flags=flags,
    )
