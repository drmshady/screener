"""Assemble the deterministic ``BriefModel`` for one target session.

Reuses existing outputs (portfolio holdings/totals, holding risk, feature-014
sentiment, regime, market events) — no new financial logic (FR-002). The genuinely
new work here is pure synthesis: mapping the existing `PortfolioTotals` +
`PortfolioHolding` outputs into the brief's `PortfolioStatusSection`, deriving the
holdings-attention list by the documented precedence, and (US2) folding in the
news + market-context sections. Selection of the five recommendations lives in
`recommend.py`; rendering in `render.py`.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from ..lib.disclaimer import DISCLAIMER_TEXT
from ..lib.flags import brief_directive_enabled
from ..models.brief import (
    AttentionItem,
    AttentionReason,
    BriefModel,
    HoldingLine,
    MarketContextLine,
    NewsItem,
    PortfolioStatusSection,
)
from ..models.portfolio import (
    PortfolioCaps,
    PortfolioHolding,
    PortfolioHoldingsRequest,
    PortfolioTotals,
)
from . import recommend

# --- Documented attention constants (data-model §AttentionItem) ------------

# A holding is "near" its stop when the current-condition stop distance is within
# this fraction. Purely a synthesis threshold over numbers the app produces.
STOP_PROXIMITY_PCT = 0.05
# Level-block statuses that escalate an open holding to the `managing` stage
# (mirrors the frontend `holdingNeedsAttention`).
_ATTENTION_LEVEL_STATUSES = {"stop_breached", "target_reached", "gains_protected"}
_MOMENTUM_SLUG = "midterm_52w_high_momentum"


# --- Portfolio config from the single-owner blob ---------------------------


def _blob_state() -> dict[str, Any]:
    from ..data.portfolio_store import load_portfolio_state

    envelope = load_portfolio_state() or {}
    return (envelope.get("state") or {}) if isinstance(envelope, dict) else {}


def _caps_from_settings(settings: dict[str, Any]) -> PortfolioCaps:
    try:
        return PortfolioCaps(
            per_position_cap_pct=float(settings.get("per_position_cap_pct", 0.10)),
            per_sector_cap_pct=float(settings.get("per_sector_cap_pct", 0.25)),
        )
    except Exception:
        return PortfolioCaps()


def _num(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _watchlist_tickers(state: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for entry in state.get("watchlist") or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("state") == "dismissed":
            continue
        ticker = str(entry.get("ticker", "")).strip().upper()
        if ticker:
            out.append(ticker)
    # Deterministic, de-duplicated.
    return sorted(dict.fromkeys(out))


def _assemble_portfolio_inputs() -> tuple[
    list[PortfolioHolding], PortfolioTotals, str | None, dict[str, Any], list[str]
]:
    """Price the owner's holdings via the SAME path the app uses so the brief's
    numbers are byte-identical to the in-app portfolio (research Decision 8).

    Cash-first capital model (feature 016): when `available_cash` is set the
    effective total capital derives as cash + Σ holding market value, matching the
    frontend `effectiveTotalCapital`. We price once to learn market value, then
    re-run with the derived total so the risk figures are correct.
    """
    from ..api.portfolio import _assemble_holdings  # lazy: heavy import graph

    state = _blob_state()
    settings = state.get("settings") or {}
    portfolio_cfg = state.get("portfolio") or {}
    caps = _caps_from_settings(settings)
    available_cash = _num(portfolio_cfg.get("available_cash"))
    entered_total = _num(portfolio_cfg.get("total_capital")) or Decimal("1")

    first_capital = entered_total if entered_total > 0 else Decimal("1")
    holdings, totals, newest, _trades = _assemble_holdings(
        PortfolioHoldingsRequest(
            total_capital=first_capital,
            caps=caps,
            available_cash=available_cash,
        )
    )

    if available_cash is not None:
        market_value = sum(
            (
                (h.current_price or h.avg_cost) * h.net_quantity
                for h in holdings
                if h.status == "open"
            ),
            Decimal("0"),
        )
        effective_total = available_cash + market_value
        if effective_total > 0 and effective_total != first_capital:
            holdings, totals, newest, _trades = _assemble_holdings(
                PortfolioHoldingsRequest(
                    total_capital=effective_total,
                    caps=caps,
                    available_cash=available_cash,
                )
            )

    return holdings, totals, newest, state, _watchlist_tickers(state)


# --- Attention derivation (pure) -------------------------------------------


def _needs_managing(holding: PortfolioHolding) -> bool:
    if holding.risk is not None and holding.risk.over_risk:
        return True
    if holding.levels is None:
        return False
    blocks = [
        holding.levels.original_plan,
        holding.levels.current_condition,
        holding.levels.trailing,
    ]
    return any(b is not None and b.status in _ATTENTION_LEVEL_STATUSES for b in blocks)


def _holding_stage(holding: PortfolioHolding) -> str:
    if holding.status != "open":
        return holding.status
    return "managing" if _needs_managing(holding) else "owned"


def build_attention(
    holdings: list[PortfolioHolding],
    totals: PortfolioTotals,
    pipeline: dict[str, Any] | None = None,
) -> list[AttentionItem]:
    """Derive the holdings-needing-attention list, ordered by the documented
    precedence (risk/heat breach → stop proximity → stage change), tie-broken by
    `(severity desc, ticker asc)`. At most one item per ticker (highest reason)."""
    open_holdings = [h for h in holdings if h.status == "open"]

    # Aggregate heat breach: flag the single largest-risk holding when the
    # portfolio's open risk exceeds the ceiling (heat_headroom < 0).
    heat_ticker: str | None = None
    if totals.heat_headroom_pct < 0 and open_holdings:
        ranked = sorted(
            open_holdings,
            key=lambda h: (
                -(float(h.risk.actual_capital_at_risk) if h.risk else 0.0),
                h.ticker,
            ),
        )
        heat_ticker = ranked[0].ticker

    items: list[tuple[int, int, str, AttentionItem]] = []  # (tier, -severity, ticker, item)
    for holding in open_holdings:
        reason: AttentionReason | None = None
        detail = ""
        severity = 0
        tier = 2

        if holding.ticker == heat_ticker:
            reason = AttentionReason.HEAT_BREACH
            over = -totals.heat_headroom_pct
            detail = (
                f"portfolio open risk {totals.total_capital_at_risk_pct:.0%} exceeds the "
                f"{totals.heat_ceiling_pct:.0%} ceiling"
            )
            severity = int(round(over * 10000)) + 1_000_000
            tier = 0
        elif holding.risk is not None and holding.risk.over_risk:
            reason = AttentionReason.RISK_BREACH
            detail = (
                f"capital at risk {holding.risk.actual_capital_at_risk_pct:.0%} exceeds the "
                f"per-trade budget ({holding.risk.binding_constraint})"
            )
            severity = int(round(holding.risk.actual_capital_at_risk_pct * 10000))
            tier = 0
        else:
            current = holding.levels.current_condition if holding.levels else None
            if current is not None and current.status == "stop_breached":
                reason = AttentionReason.STOP_PROXIMITY
                detail = "price has breached the current stop"
                severity = 100_000
                tier = 1
            elif (
                current is not None
                and current.status == "holding"
                and current.distance_to_stop_pct is not None
                and current.distance_to_stop_pct <= STOP_PROXIMITY_PCT
            ):
                reason = AttentionReason.STOP_PROXIMITY
                detail = f"within {current.distance_to_stop_pct:.0%} of the current stop"
                severity = int(round((STOP_PROXIMITY_PCT - current.distance_to_stop_pct) * 100000))
                tier = 1
            elif _holding_stage(holding) == "managing":
                reason = AttentionReason.STAGE_CHANGE
                detail = "stage: managing (a level has moved past a calm holding status)"
                severity = 0
                tier = 2

        if reason is not None:
            items.append(
                (
                    tier,
                    -severity,
                    holding.ticker,
                    AttentionItem(
                        ticker=holding.ticker,
                        reason_code=reason,
                        detail=detail,
                        severity=severity,
                    ),
                )
            )

    items.sort(key=lambda row: (row[0], row[1], row[2]))
    return [row[3] for row in items]


# --- Portfolio section (pure) ----------------------------------------------


def _holding_line(holding: PortfolioHolding) -> HoldingLine:
    return HoldingLine(
        ticker=holding.ticker,
        quantity=holding.net_quantity,
        avg_cost=holding.avg_cost,
        current_price=holding.current_price,
        unrealized_pnl=holding.unrealized_pl,
        unrealized_pnl_pct=holding.unrealized_pl_pct,
        status=_holding_stage(holding),
    )


def build_portfolio_section(
    holdings: list[PortfolioHolding],
    totals: PortfolioTotals,
    pipeline: dict[str, Any] | None = None,
) -> PortfolioStatusSection:
    """Map the existing holdings/totals outputs into the brief status section."""
    open_holdings = [h for h in holdings if h.status == "open"]
    return PortfolioStatusSection(
        total_value=totals.total_invested,
        realized_pnl=totals.realized_pnl,
        unrealized_pnl=totals.unrealized_pnl,
        total_pnl=totals.total_pnl,
        win_rate=totals.win_rate,
        total_capital_at_risk_pct=totals.total_capital_at_risk_pct,
        heat_ceiling_pct=totals.heat_ceiling_pct,
        heat_headroom_pct=totals.heat_headroom_pct,
        holdings=[_holding_line(h) for h in open_holdings],
        attention=build_attention(holdings, totals, pipeline),
        is_empty=len(open_holdings) == 0,
    )


# --- News + market context (US2) -------------------------------------------


def _last_delivered_as_of(target_session: str) -> str | None:
    """The `data_as_of` boundary of the last delivered brief (Decision 7 window)."""
    from ..data import brief_store

    last = brief_store.load_last_delivered(target_session)
    return last.target_session if last is not None else None


def build_news(
    held_tickers: list[str],
    watched_tickers: list[str],
    since: str | None,
) -> list[NewsItem]:
    """Map the feature-014 captured-sentiment pipeline over held + watched tickers
    into `NewsItem`s. Reuse-only + on-demand generate-once (feature 017 path);
    fail-soft per ticker; empty ⇒ the renderer prints the "nothing material" copy.
    """
    from ..api.portfolio import _resolve_or_generate_sentiment
    from ..models.sentiment import SelectionOrigin

    tickers: list[str] = list(dict.fromkeys([*held_tickers, *watched_tickers]))
    if not tickers:
        return []

    held = {t.upper() for t in held_tickers}
    try:
        reports = _resolve_or_generate_sentiment(tickers, origin=SelectionOrigin.HOLDING)
    except Exception:
        reports = {}

    since_dt = _parse_date(since)
    items: list[NewsItem] = []
    for ticker in tickers:
        report = reports.get(ticker)
        if report is None:
            continue
        label = str(report.label)
        if label in {"no_signal"}:
            continue
        # Prefer the freshest sourced item's as-of; fall back to the report itself.
        source_name = "sentiment pipeline"
        as_of = ""
        newest_source = None
        for source in report.sources:
            if newest_source is None or source.published_at > newest_source.published_at:
                newest_source = source
        if newest_source is not None:
            source_name = newest_source.publisher or str(newest_source.source_class)
            as_of = newest_source.published_at.date().isoformat()
            if since_dt is not None and newest_source.published_at.date() < since_dt:
                # Older than the since-last-brief window ⇒ not repeated.
                continue
        risk_label = report.narrative_risk.label if report.narrative_risk else None
        items.append(
            NewsItem(
                tickers=[ticker],
                headline=report.narrative or f"{ticker} sentiment: {label}",
                sentiment_label=label,
                source=source_name,
                as_of=as_of or since or "",
                narrative_risk_label=risk_label,
            )
        )

    # Deterministic: held before watched, then ticker.
    items.sort(key=lambda item: (0 if item.tickers[0].upper() in held else 1, item.tickers[0]))
    return items


def build_market_context(as_of: str | None) -> MarketContextLine | None:
    """Regime verdict + near-term market events with source + as-of (US2 AC3)."""
    from ..events.service import EventsService
    from ..regime.calculator import current_regime_response

    try:
        regime = current_regime_response(as_of_date=as_of)
    except Exception:
        return None

    events: list[str] = []
    events_source = "econ calendar"
    events_as_of = ""
    try:
        market = EventsService().market_response(days_ahead=7)
        events = [
            f"{e.event_type} on {e.event_date}"
            for e in getattr(market, "events", [])
        ][:5]
        events_source = market.source_name
        events_as_of = market.source_as_of
    except Exception:
        pass

    regime_as_of = str(regime.as_of_date)
    source = f"{regime.inputs.price_source_name}; {events_source}"
    newest_as_of = max([d for d in [regime_as_of, events_as_of, as_of or ""] if d] or [""])
    return MarketContextLine(
        regime=regime.regime,
        regime_detail=regime.rule_summary,
        market_events=events,
        source=source,
        as_of=newest_as_of or regime_as_of,
    )


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except Exception:
        return None


# --- Orchestration ---------------------------------------------------------


def _collect_warnings(holdings: list[PortfolioHolding], market: MarketContextLine | None) -> list[str]:
    warnings: list[str] = []
    for holding in holdings:
        for note in holding.data_notes:
            if note not in warnings:
                warnings.append(note)
    if market is not None and "unavailable" in market.regime_detail.lower():
        warnings.append(market.regime_detail)
    return warnings


def _momentum_citation() -> list[str]:
    try:
        from ..strategies._registry import registry

        strategy = registry.get(_MOMENTUM_SLUG)
        return [strategy.citation] if strategy and strategy.citation else []
    except Exception:
        return []


def assemble_brief(
    target_session: str,
    *,
    include_news: bool = True,
) -> BriefModel:
    """Assemble the full deterministic brief for one completed session.

    Composes the portfolio-status section, the news + market-context sections
    (US2), and the five ranked recommendations (US3), then stamps the disclosures.
    `generated_at` is the only non-deterministic field and is excluded from the
    content hash (FR-013).
    """
    holdings, totals, newest_as_of, state, watched = _assemble_portfolio_inputs()
    pipeline = state.get("pipeline") or {}
    section = build_portfolio_section(holdings, totals, pipeline)

    held = [h.ticker for h in holdings if h.status == "open"]
    since = _last_delivered_as_of(target_session)
    news: list[NewsItem] = []
    market: MarketContextLine | None = None
    if include_news:
        news = build_news(held, watched, since)
        market = build_market_context(newest_as_of or target_session)

    directive = brief_directive_enabled()
    citations = _momentum_citation()
    recommendations = recommend.select_recommendations(
        section,
        news,
        directive=directive,
        held_tickers=held,
        watchlist_tickers=watched,
        citations=citations,
    )
    directive_used = any(item.citations for item in recommendations)

    warnings = _collect_warnings(holdings, market)
    as_of_candidates = [newest_as_of or target_session, target_session]
    if market is not None and market.as_of:
        as_of_candidates.append(market.as_of)
    for item in news:
        if item.as_of:
            as_of_candidates.append(item.as_of)
    data_as_of = max(d for d in as_of_candidates if d)

    return BriefModel(
        target_session=target_session,
        portfolio=section,
        news=news,
        market_context=market,
        recommendations=recommendations,
        directive=directive,
        data_as_of=data_as_of,
        disclaimer=DISCLAIMER_TEXT,
        warnings=warnings,
        citations=citations if directive_used else [],
    )
