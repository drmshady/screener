from __future__ import annotations

from decimal import Decimal, ROUND_FLOOR

from ..lib import flags
from ..models.portfolio import SizingRequest, SizingResponse, money, pct
from ..regime.calculator import current_regime_response
from .exposure import aggregate_exposure, existing_open_risk, holding_value

# Conviction-scale clamp band shared by every candidate modulator (Decision 3) —
# placeholder pending US4 calibration (research.md Decision 6).
_CONVICTION_BOOST_CAP = 1.5
_CONVICTION_SHRINK_FLOOR = 0.5


def _regime_risk_scale() -> float:
    """Opt-in regime-aware risk-budget scale (Decision 7, FR-011): 1.0 unless the
    overlay is enabled and the existing regime signal reads unfavorable
    ("Trending down"). Fails open to 1.0 whenever the overlay is off, the regime
    is unavailable, or the lookup errors — this is an informational scale, never
    a blocking gate."""
    if not flags.regime_risk_budget_enabled():
        return 1.0
    try:
        regime = current_regime_response().regime
    except Exception:
        return 1.0
    return flags.regime_risk_budget_unfavorable() if regime == "Trending down" else 1.0


def _effective_risk_per_trade_fraction() -> float:
    return flags.risk_per_trade_fraction() * _regime_risk_scale()


def _cap_amount(total_capital: Decimal, cap_pct: float) -> Decimal:
    return money(total_capital * Decimal(str(cap_pct)))


def _floor_shares(value: Decimal) -> int:
    if value <= 0:
        return 0
    return int(value.to_integral_value(rounding=ROUND_FLOOR))


def _synthetic_stop_distance(request: SizingRequest) -> Decimal:
    """A deliberately wide synthetic stop distance for the no-stop case so the
    position sized against it is small — never the full cap. Uses the request
    volatility when supplied, else the inverse-vol baseline, scaled by the
    fallback ATR multiplier (Decision 6, FR-009)."""
    vol = (
        request.volatility
        if request.volatility is not None and request.volatility > 0
        else flags.sizing_inverse_vol_baseline()
    )
    distance = money(
        request.entry * Decimal(str(vol)) * Decimal(str(flags.sizing_fallback_atr_mult()))
    )
    return distance if distance > 0 else money(request.entry)


def _apply_heat(
    request: SizingRequest,
    final_shares: int,
    per_share_risk: Decimal,
    binding_constraint: str,
) -> tuple[int, str, float]:
    """Bound the aggregate open risk (portfolio heat) by the configured ceiling.

    Sums the existing holdings' conservative synthetic risk-to-stop plus the
    proposed position's risk; when the total would exceed the ceiling, reduce the
    proposed shares and report ``portfolio_heat`` as the binding constraint
    (Decision 6, FR-010). Returns (shares, binding_constraint, heat_after_pct)."""
    if request.total_capital <= 0:
        return final_shares, binding_constraint, 0.0

    existing_risk = existing_open_risk(request.holdings)
    ceiling_amount = money(
        request.total_capital * Decimal(str(flags.portfolio_heat_ceiling()))
    )
    proposed_risk = money(per_share_risk * Decimal(final_shares))

    if per_share_risk > 0 and existing_risk + proposed_risk > ceiling_amount:
        allowed = ceiling_amount - existing_risk
        max_shares_by_heat = _floor_shares(allowed / per_share_risk) if allowed > 0 else 0
        if max_shares_by_heat < final_shares:
            final_shares = max_shares_by_heat
            binding_constraint = "portfolio_heat"
            proposed_risk = money(per_share_risk * Decimal(final_shares))

    heat_after_pct = float((existing_risk + proposed_risk) / request.total_capital)
    return final_shares, binding_constraint, heat_after_pct


def _heat_after_pct(
    request: SizingRequest, shares: int, per_share_risk: Decimal
) -> float:
    """Aggregate open-risk fraction after committing ``shares`` at ``per_share_risk``."""
    if request.total_capital <= 0:
        return 0.0
    existing_risk = existing_open_risk(request.holdings)
    proposed_risk = money(per_share_risk * Decimal(shares))
    return float((existing_risk + proposed_risk) / request.total_capital)


def _apply_available_cash(
    request: SizingRequest,
    final_shares: int,
    per_share_risk: Decimal,
    binding_constraint: str,
    heat_after_pct: float,
) -> tuple[int, str, float]:
    """Cap the position at the owner's available cash (Feature 016, US2).

    Absent ``available_cash`` is byte-identical to today. When present, reduce
    ``final_shares`` so ``shares × entry ≤ available_cash`` and report
    ``available_cash`` as the binding constraint — but only when cash is the
    tightest limit (a tighter risk/position/sector/heat constraint stands)."""
    if request.available_cash is None:
        return final_shares, binding_constraint, heat_after_pct

    max_shares_by_cash = (
        _floor_shares(request.available_cash / request.entry)
        if request.entry > 0
        else 0
    )
    if max_shares_by_cash < final_shares:
        final_shares = max_shares_by_cash
        binding_constraint = "available_cash"
        heat_after_pct = _heat_after_pct(request, final_shares, per_share_risk)
    return final_shares, binding_constraint, heat_after_pct


def _conservative_fallback(request: SizingRequest) -> SizingResponse:
    """No valid stop supplied. The pre-US4 branch fell open to a full cap-fill —
    sizing *largest* exactly when risk information was weakest. Instead, size a
    small position against a conservative synthetic stop distance, still hard-
    bounded by the caps and the portfolio-heat ceiling (Decision 6, FR-009/010).
    The pre-existing "cannot fit one share within caps" error branch is preserved
    (the sizing endpoint surfaces it as a 422)."""
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

    synthetic_stop = _synthetic_stop_distance(request)
    risk_budget = money(
        request.total_capital * Decimal(str(_effective_risk_per_trade_fraction()))
    )
    target_shares = _floor_shares(risk_budget / synthetic_stop) if synthetic_stop > 0 else 0
    max_shares_by_cap = (
        _floor_shares(max_trade_value / request.entry) if max_trade_value > 0 else 0
    )

    if max_shares_by_cap < target_shares:
        final_shares = max_shares_by_cap
        binding_constraint = (
            "position_cap" if remaining_position_room <= remaining_sector_room else "sector_cap"
        )
    else:
        final_shares = target_shares
        binding_constraint = "conservative_fallback"

    final_shares, binding_constraint, heat_after_pct = _apply_heat(
        request, final_shares, synthetic_stop, binding_constraint
    )
    final_shares, binding_constraint, heat_after_pct = _apply_available_cash(
        request, final_shares, synthetic_stop, binding_constraint, heat_after_pct
    )

    trade_value = money(request.entry * Decimal(final_shares))
    resulting_position_value = current_position_value + trade_value
    resulting_sector_value = current_sector_value + trade_value
    resulting_position_pct = pct(resulting_position_value, request.total_capital)
    resulting_sector_pct = pct(resulting_sector_value, request.total_capital)
    caps_respected = (
        resulting_position_pct <= request.caps.per_position_cap_pct
        and resulting_sector_pct <= request.caps.per_sector_cap_pct
    )

    reasoning = (
        "No valid stop supplied; used a conservative fallback stop distance of "
        f"${synthetic_stop} (a wide volatility-based estimate) so the position is "
        "small rather than cap-filled. Binding constraint: "
        f"{binding_constraint.replace('_', ' ')}."
    )

    return SizingResponse(
        suggested_shares=final_shares,
        suggested_position_value=trade_value,
        resulting_position_pct_of_capital=resulting_position_pct,
        resulting_sector_pct_of_capital=resulting_sector_pct,
        caps_respected=caps_respected,
        reasoning=reasoning,
        risk_per_trade_target=risk_budget,
        risk_per_share=synthetic_stop,
        conviction_signal="none",
        conviction_adjustment="none",
        binding_constraint=binding_constraint,
        conviction_used=False,
        conservative_fallback=True,
        reward_to_risk=None,
        portfolio_heat_after_pct=heat_after_pct,
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
    effective_fraction = _effective_risk_per_trade_fraction()
    risk_budget = money(request.total_capital * Decimal(str(effective_fraction)))
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

    final_shares, binding_constraint, heat_after_pct = _apply_heat(
        request, final_shares, risk_per_share, binding_constraint
    )
    final_shares, binding_constraint, heat_after_pct = _apply_available_cash(
        request, final_shares, risk_per_share, binding_constraint, heat_after_pct
    )

    trade_value = money(request.entry * Decimal(final_shares))
    resulting_position_value = current_position_value + trade_value
    resulting_sector_value = current_sector_value + trade_value
    resulting_position_pct = pct(resulting_position_value, request.total_capital)
    resulting_sector_pct = pct(resulting_sector_value, request.total_capital)

    reasoning = (
        f"Risk-per-trade target is {target_shares} shares (risking "
        f"{effective_fraction:.2%} of capital across the "
        f"${risk_per_share} stop distance)"
    )
    if effective_fraction < flags.risk_per_trade_fraction():
        reasoning += (
            "; risk budget scaled down for the current unfavorable market regime"
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
        conservative_fallback=False,
        reward_to_risk=None,
        portfolio_heat_after_pct=heat_after_pct,
    )


def size_position(request: SizingRequest) -> SizingResponse:
    if (
        request.stop_loss is None
        or request.stop_loss <= 0
        or request.stop_loss >= request.entry
    ):
        return _conservative_fallback(request)
    return _risk_based_sizing(request)
