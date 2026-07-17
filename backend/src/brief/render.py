"""Render a ``BriefModel`` to deterministic text + minimal HTML.

`generated_at` is excluded (it is never read here), so re-runs on the same
snapshot render byte-identically (FR-013, SC-005). Recommendation wording is
authored in `recommend.py` (neutral by default, direct + cited when the
single-owner carve-out holds); this module lays the sections out and re-asserts
the no-directive lint on the neutral path (FR-006). Every brief carries
`data_as_of` + the non-advice disclaimer and surfaces active warnings verbatim.
"""
from __future__ import annotations

import html as _html
from decimal import Decimal

from ..lib.disclaimer import DISCLAIMER_TEXT
from ..models.brief import BriefModel
from ..sentiment.narrative import validate_no_directive_language

DISCLAIMER = DISCLAIMER_TEXT


def _money(value: Decimal | None) -> str:
    if value is None:
        return "—"
    return f"${value:,.2f}"


def _pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.1%}"


def _portfolio_lines(brief: BriefModel) -> list[str]:
    section = brief.portfolio
    if section.is_empty:
        return ["Portfolio status", "  Your portfolio is empty — no open holdings to report."]

    lines = ["Portfolio status"]
    lines.append(f"  Total value: {_money(section.total_value)}")
    lines.append(f"  Total P&L: {_money(section.total_pnl)}")
    if section.win_rate is not None:
        lines.append(f"  Win rate: {_pct(section.win_rate)}")
    lines.append(
        f"  Open risk (heat): {_pct(section.total_capital_at_risk_pct)} of "
        f"{_pct(section.heat_ceiling_pct)} ceiling "
        f"(headroom {_pct(section.heat_headroom_pct)})"
    )
    lines.append("  Holdings:")
    for holding in section.holdings:
        lines.append(
            f"    {holding.ticker}: {holding.quantity} @ {_money(holding.avg_cost)} "
            f"(now {_money(holding.current_price)}, "
            f"P&L {_money(holding.unrealized_pnl)} / {_pct(holding.unrealized_pnl_pct)}, "
            f"{holding.status})"
        )

    lines.append("  Needs attention:")
    if section.attention:
        for item in section.attention:
            lines.append(f"    {item.ticker} [{item.reason_code.value}]: {item.detail}")
    else:
        lines.append("    Nothing needs attention.")
    return lines


def _news_lines(brief: BriefModel) -> list[str]:
    lines = ["News & sentiment"]
    if not brief.news:
        lines.append("  Nothing material for your held or watched names in this window.")
        return lines
    for item in brief.news:
        tickers = ", ".join(item.tickers)
        label = item.sentiment_label or "signal"
        lines.append(f"    {tickers} [{label}] — {item.headline}")
        lines.append(f"      source: {item.source}; as of {item.as_of}")
    return lines


def _market_lines(brief: BriefModel) -> list[str]:
    lines = ["Market context"]
    market = brief.market_context
    if market is None:
        lines.append("  Market context is unavailable for this session.")
        return lines
    lines.append(f"  Regime: {market.regime} — {market.regime_detail}")
    if market.market_events:
        lines.append(f"  Near-term events: {', '.join(market.market_events)}")
    lines.append(f"  source: {market.source}; as of {market.as_of}")
    return lines


def _recommendation_lines(brief: BriefModel) -> list[str]:
    lines = ["Five things to review"]
    for item in brief.recommendations:
        # Re-assert the no-directive lint on the neutral path (SC-004).
        if not brief.directive:
            validate_no_directive_language(item.text)
        line = f"  {item.rank}. {item.text}"
        if item.citations:
            line += f" [{'; '.join(item.citations)}]"
        lines.append(line)
    return lines


def render_text(brief: BriefModel) -> str:
    blocks: list[list[str]] = [
        [f"Daily portfolio brief — {brief.target_session}"],
        _portfolio_lines(brief),
        _news_lines(brief),
        _market_lines(brief),
        _recommendation_lines(brief),
    ]
    if brief.warnings:
        blocks.append(["Data notes", *[f"  {w}" for w in brief.warnings]])
    footer = [f"Data as of {brief.data_as_of}", brief.disclaimer]
    if brief.citations:
        footer.append("Citations: " + "; ".join(brief.citations))
    blocks.append(footer)
    return "\n\n".join("\n".join(block) for block in blocks)


def render_html(brief: BriefModel, text: str) -> str:
    escaped = _html.escape(text)
    body = escaped.replace("\n", "<br>\n")
    return (
        "<html><body style=\"font-family:system-ui,Arial,sans-serif;"
        "white-space:normal;\">\n"
        f"<pre style=\"font-family:inherit;white-space:pre-wrap;\">{body}</pre>\n"
        "</body></html>"
    )


def render_subject(brief: BriefModel) -> str:
    return f"Daily portfolio brief — {brief.target_session}"


def render_brief(brief: BriefModel) -> tuple[str, str, str]:
    """Return ``(subject, text_body, html_body)`` — deterministic for a given brief."""
    subject = render_subject(brief)
    text = render_text(brief)
    html = render_html(brief, text)
    return subject, text, html
