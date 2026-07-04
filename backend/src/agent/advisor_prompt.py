from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from ..lib.disclaimer import DISCLAIMER_TEXT
from ..models.sentiment import NarrativeSource, SentimentLabel, SentimentReport
from ..models.strategy import AnalyzeResponse, Strategy
from ..sentiment.narrative import validate_no_directive_language

# ---------------------------------------------------------------------------
# Input gatherers (read-only; no recomputation of any candidate figure)
# ---------------------------------------------------------------------------

_BACKTEST_DIR = Path(__file__).resolve().parents[2] / "data" / "backtests"
_BACKTEST_PATH = _BACKTEST_DIR / "midterm_52w_high_momentum.json"


def load_survivorship_status(
    path: Path | None = None, slug: str | None = None
) -> dict:
    """Read the backtest artifact's survivorship-bias status.

    Returns ``{"confirmed": bool, "passed": bool | None, "note": str}``. When the
    artifact is missing/unreadable, ``confirmed`` is False and the honesty block
    states the status is unconfirmed (it never implies the backtest is clean).
    The artifact is selected by ``slug`` (defaulting to the momentum strategy for
    back-compatibility) or an explicit ``path``.
    """
    p = path or (_BACKTEST_DIR / f"{slug}.json" if slug else _BACKTEST_PATH)
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
        item = payload["bias_check"]["survivorship_bias"]
        return {
            "confirmed": True,
            "passed": bool(item.get("passed")),
            "note": str(item.get("note", "")),
        }
    except Exception:
        return {
            "confirmed": False,
            "passed": None,
            "note": "backtest artifact unavailable — survivorship status could not be confirmed",
        }


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------

_DIRECTIVE_WORDS = ("buy", "sell", "recommended", "strong buy")


def _reward_risk(entry: str, stop_loss: str, take_profit: str) -> str | None:
    try:
        e, s, t = float(entry), float(stop_loss), float(take_profit)
        risk = e - s
        if risk <= 0:
            return None
        return f"{(t - e) / risk:.2f}R"
    except (TypeError, ValueError):
        return None


def _fmt_num(x, *, pct: bool = False) -> str | None:
    if x is None:
        return None
    if pct:
        return f"{x * 100:.1f}%"
    ax = abs(x)
    if ax != 0 and (ax >= 1e6 or ax < 1e-3):
        return f"{x:.3e}"
    return f"{x:.4g}"


def _date_part(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:10] if len(text) >= 10 else text


def _material_input_freshness(
    obj,
    *,
    default_as_of: str | None,
    regime_as_of: str | None = None,
) -> dict[str, str]:
    return _material_input_freshness_from_raw(
        getattr(obj, "material_input_freshness", None) or {},
        default_as_of=default_as_of,
        regime_as_of=regime_as_of,
    )


def _material_input_freshness_from_raw(
    raw,
    *,
    default_as_of: str | None,
    regime_as_of: str | None = None,
) -> dict[str, str]:
    fallback = _date_part(default_as_of) or "unavailable"
    return {
        "prices": _date_part(raw.get("prices")) or fallback,
        "fundamentals": _date_part(raw.get("fundamentals")) or fallback,
        "regime": _date_part(raw.get("regime")) or _date_part(regime_as_of) or fallback,
    }


def _material_input_freshness_lines(
    obj,
    *,
    default_as_of: str | None,
    regime_as_of: str | None = None,
) -> list[str]:
    freshness = _material_input_freshness(
        obj, default_as_of=default_as_of, regime_as_of=regime_as_of
    )
    return [
        f"- Prices data_as_of: {freshness['prices']}",
        f"- Fundamentals data_as_of: {freshness['fundamentals']}",
        f"- Regime as-of: {freshness['regime']}",
    ]


def _material_input_freshness_summary(
    obj,
    *,
    default_as_of: str | None,
    regime_as_of: str | None = None,
) -> str:
    freshness = _material_input_freshness(
        obj, default_as_of=default_as_of, regime_as_of=regime_as_of
    )
    return (
        "Material input freshness: "
        f"prices {freshness['prices']}; "
        f"fundamentals {freshness['fundamentals']}; "
        f"regime {freshness['regime']}."
    )


def _diagnostics_lines(c) -> list[str]:
    """Ranking inputs + raw fundamentals so the advisor can rank/triage, not just
    read risk geometry. Only present values are shown; missing ones are omitted
    (they are unavailable on the free data tier, not zero)."""
    rank_bits: list[str] = []
    score = getattr(c, "score", None)
    if score is not None:
        rank_bits.append(f"score {_fmt_num(score)}")
    if getattr(c, "return_12_1", None) is not None:
        rank_bits.append(f"12-1 momentum {_fmt_num(c.return_12_1, pct=True)}")
    if getattr(c, "vol_scalar", None) is not None:
        rank_bits.append(f"vol_scalar {_fmt_num(c.vol_scalar)}")
    if getattr(c, "dist_to_high", None) is not None:
        rank_bits.append(f"dist_to_high {_fmt_num(c.dist_to_high, pct=True)}")
    # Value-composite diagnostics (midterm_value_composite); shown only when present.
    if getattr(c, "value_composite", None) is not None:
        rank_bits.append(f"value composite {_fmt_num(c.value_composite)}")
    if getattr(c, "f_score", None) is not None:
        evaluable = getattr(c, "f_score_evaluable", None)
        if evaluable is not None:
            ev = int(evaluable)
            note = f" ({ev}/9 components evaluable" + (
                "; too few to be reliable)" if ev < 5 else ")"
            )
        else:
            note = ""
        rank_bits.append(f"Piotroski F-Score {int(c.f_score)}/9{note}")

    fund_bits: list[str] = []
    if getattr(c, "debt_to_equity", None) is not None:
        fund_bits.append(f"D/E {_fmt_num(c.debt_to_equity)}")
    if getattr(c, "fcf_ttm", None) is not None:
        fund_bits.append(f"FCF_ttm {_fmt_num(c.fcf_ttm)}")
    if getattr(c, "gp_to_assets", None) is not None:
        fund_bits.append(f"gp/assets {_fmt_num(c.gp_to_assets)}")
    if getattr(c, "asset_growth", None) is not None:
        fund_bits.append(f"asset_growth {_fmt_num(c.asset_growth, pct=True)}")
    if getattr(c, "book_to_market", None) is not None:
        fund_bits.append(f"book/market {_fmt_num(c.book_to_market)}")
    if getattr(c, "earnings_yield", None) is not None:
        fund_bits.append(f"earnings yield {_fmt_num(c.earnings_yield, pct=True)}")
    if getattr(c, "cashflow_yield", None) is not None:
        fund_bits.append(f"cash-flow yield {_fmt_num(c.cashflow_yield, pct=True)}")
    if getattr(c, "sales_yield", None) is not None:
        fund_bits.append(f"sales yield {_fmt_num(c.sales_yield)}")
    if getattr(c, "atr", None) is not None:
        fund_bits.append(f"ATR {_fmt_num(c.atr)}")

    lines: list[str] = []
    if rank_bits:
        lines.append("- Ranking inputs: " + " | ".join(rank_bits))
    if fund_bits:
        lines.append("- Fundamentals: " + " | ".join(fund_bits))
    return lines


_EMBEDDED_SENTIMENT_NOTE = (
    "Any 'External context — sentiment & narrative' section embedded below is "
    "informational, dated, sourced external context: it MUST NOT overwrite or override "
    "any computed gate result, rank, price level, or position size — treat it only as "
    "risk-narrative color."
)


def _task_instruction(directive: bool) -> str:
    if directive:
        base = (
            "TASK (personal-use, single-user — directive guidance permitted): You are an "
            "expert advisor for the strategy below. Walk the gate results in order, derive/"
            "confirm the entry, stop, and take-profit, then give a concrete directive call "
            "(take / pass / size) with your explicit confidence and the single biggest risk "
            "that would change it. Use only the numbers provided here — do not compute or "
            "invent figures. End with the honesty caveats. This guidance is for the single "
            "owner of this tool only and must not be redistributed."
        )
    else:
        base = (
            "TASK: You are an expert analyst for the strategy below. Walk the gate results in "
            "order and explain neutrally how this name scores against the strategy's rules "
            "(treat it as a screen match / candidate for further research, not a recommendation). "
            "Use only the numbers provided here — do not compute or invent figures. End with the "
            "honesty caveats."
        )
    return base + " " + _EMBEDDED_SENTIMENT_NOTE


def _strategy_context(strategy: Strategy, gate_names: list[str]) -> str:
    hold = strategy.holding_period_days or {}
    lines = [
        "## Strategy",
        f"- Name: {strategy.name} ({strategy.slug})",
        f"- Core citation: {strategy.citation}",
        f"- Timeframe: {strategy.timeframe}",
    ]
    if hold:
        lines.append(
            f"- Holding period: {hold.get('min', '?')}–{hold.get('max', '?')} days"
        )
    lines.append(
        "- Universe-wide liquidity gate applies first (ADV ≥ $1M 20-day, price ≥ $5)."
    )
    if gate_names:
        lines.append("- Gates evaluated: " + ", ".join(gate_names) + ".")
    mps = strategy.parameters.get("max_per_sector") if strategy.parameters else None
    max_per_sector = getattr(mps, "default", 5)
    if strategy.slug == "midterm_value_composite":
        ranking = (
            "survivors are scored by the value composite (mean cross-sectional "
            "percentile rank of book/market, earnings, cash-flow and sales yields; "
            "higher = cheaper)"
        )
    elif strategy.slug == "midterm_52w_high_momentum":
        ranking = (
            "survivors are scored by return_12_1 × vol_scalar / (1 + dist_to_high) "
            "(higher = stronger)"
        )
    else:
        ranking = "survivors are scored by the strategy's ranking expression (higher = stronger)"
    lines.append(
        f"- Ranking: {ranking}, then kept to at most {max_per_sector} per sector "
        "(sector-relative ranking). Any names beyond a sector's cap were dropped before this list."
    )
    lines.append("- Modifications (each with its own source):")
    for mod in strategy.modifications:
        lines.append(f"  - {mod.name} — {mod.description} [{mod.citation}]")
    return "\n".join(lines)


def _candidate_block(result: AnalyzeResponse, *, regime_as_of: str | None = None) -> str:
    rr = _reward_risk(result.entry, result.stop_loss, result.take_profit)
    lines = [
        "## Candidate result",
        f"- Ticker: {result.ticker} — {result.name} ({result.sector})",
        f"- Data as of: {result.as_of}",
        *_material_input_freshness_lines(
            result, default_as_of=result.as_of, regime_as_of=regime_as_of
        ),
        f"- Would be selected by the strategy: {'yes' if result.would_be_selected else 'no'}",
        f"- Current price: {result.current_price}",
        f"- Entry: {result.entry}",
        f"- Stop: {result.stop_loss}"
        + (
            f" (tighter alternative: {result.tighter_stop_loss})"
            if result.tighter_stop_loss
            else ""
        ),
        f"- Take-profit: {result.take_profit}",
    ]
    if getattr(result, "data_integrity_warnings", []):
        lines.append("### DATA INTEGRITY WARNING (verify before acting)")
        for w in result.data_integrity_warnings:
            lines.append(f"- {w.reason}")
    if rr is not None:
        lines.append(f"- Reward:risk = {rr}")
    lines.extend(_diagnostics_lines(result))
    lines.extend(_entry_timing_lines(result))
    lines.extend(_skipped_gate_lines(result))
    return "\n".join(lines)


def _skipped_gate_lines(obj) -> list[str]:
    """Feature 012 US2 (FR-014): carry the candidate's skipped preferred gates
    (gate + reason) verbatim into the prompt. Neutral, zero-directive; only
    present when expanded coverage retained the name on a non-passing preferred
    gate."""
    skipped = getattr(obj, "skipped_gates", None) or []
    if not skipped:
        return []
    items = "; ".join(f"{s.gate} ({s.reason})" for s in skipped)
    return [
        "- Skipped preferred gates (expanded coverage — retained and demoted below "
        "all clean names, NOT a pass): " + items
    ]


def _entry_timing_lines(obj) -> list[str]:
    """Feature 012 US1 (FR-023): carry the momentum entry-timing overlay into the
    prompt as an objective technical STATE — never a directive. Present only when
    the candidate has an `entry_timing` classification (momentum-only; absent for
    value / default-off, so other payloads are unchanged). Every rule is attributed
    to its source (Minervini 2013 base/pivot/breakout; Faber 2007 SMA-200
    extension). Mirrors Claude-Project custom-instruction rule #8."""
    et = getattr(obj, "entry_timing", None)
    if et is None:
        return []
    state_label = et.state.replace("_", "-").upper()
    lines = [
        "- Entry-timing (momentum technical STATE, not a directive — Minervini 2013 "
        f"base/pivot/breakout, Faber 2007 SMA-200 extension): {state_label} — {et.summary}",
    ]
    comps = "; ".join(f"{c.name}={c.status.upper()} ({c.reason})" for c in et.components)
    if comps:
        lines.append("  - Components: " + comps)
    triggered = [d for d in et.disqualifiers if d.triggered]
    if triggered:
        bits = []
        for d in triggered:
            suffix = (
                " [forces not-entry-ready]"
                if d.forces_not_entry_ready
                else " — describes risk, not a directive"
            )
            bits.append(f"{d.name} ({d.reason}){suffix}")
        lines.append("  - Disqualifiers: " + "; ".join(bits))
    d = et.diagnostics
    diag: list[str] = []
    if d.base_type and d.base_type != "none":
        diag.append(f"base {d.base_type}")
    if d.base_length_weeks is not None:
        diag.append(f"length {d.base_length_weeks:.0f}w")
    if d.base_depth is not None:
        diag.append(f"depth {d.base_depth:.0%}")
    if d.pivot is not None:
        diag.append(f"pivot {d.pivot:.2f}")
    if d.breakout_volume_ratio is not None:
        diag.append(f"breakout vol {d.breakout_volume_ratio:.2f}x")
    if d.dist_above_pivot is not None:
        diag.append(f"vs pivot {d.dist_above_pivot:+.0%}")
    if d.dist_above_sma_200 is not None:
        diag.append(f"vs SMA-200 {d.dist_above_sma_200:+.0%}")
    if diag:
        lines.append("  - Base/pivot diagnostics: " + ", ".join(diag))
    if et.state == "entry_undetermined":
        lines.append(
            "  - Note: entry-undetermined = missing/unclassifiable data, not a weak setup."
        )
    return lines


def _gate_breakdown(result: AnalyzeResponse) -> str:
    lines = ["## Gate-by-gate breakdown"]
    for g in result.gate_results:
        tag = {"pass": "PASS", "fail": "FAIL", "skipped": "SKIPPED"}.get(
            g.status, g.status.upper()
        )
        suffix = (
            "  [not a real pass — gate could not be evaluated on missing data]"
            if g.status == "skipped"
            else ""
        )
        lines.append(f"- [{tag}] {g.gate} — {g.detail}{suffix}")
    return "\n".join(lines)


def _regime_block(strategy: Strategy, regime: str | None) -> str:
    if not regime:
        return (
            "## Market regime\n- Current regime: unavailable for this snapshot "
            "(treat regime-dependent favorability as unknown)."
        )
    fav = (strategy.regime_favorability or {}).get(regime, "Neutral")
    return (
        "## Market regime\n"
        f"- Current regime: {regime}\n"
        f"- Favorability for this strategy: {fav}"
    )


def _honesty_block(
    result: AnalyzeResponse,
    survivorship: dict,
    directive: bool,
    *,
    regime_as_of: str | None = None,
) -> str:
    lines = ["## Honesty & limitations (read before any performance judgment)"]

    if not survivorship.get("confirmed"):
        lines.append(
            "- Survivorship status: UNCONFIRMED — the backtest artifact was unavailable, "
            "so historical performance cannot be vouched for. Do not assume it is clean."
        )
    elif survivorship.get("passed") is False:
        note = survivorship.get("note") or ""
        lines.append(
            "- Survivorship bias: the backtest FAILS its survivorship check, so historical "
            "performance (hit-rate, returns) is OPTIMISTIC — delisted/failed companies are "
            "absent from the data." + (f" Detail: {note}" if note else "")
        )
    else:
        lines.append(
            "- Survivorship bias: the backtest passes its survivorship check on this snapshot."
        )

    skipped = [g.gate for g in result.gate_results if g.status == "skipped"]
    if skipped:
        lines.append(
            "- Data gaps: these gates were skipped/passed-through on missing data and did NOT "
            "genuinely pass: " + ", ".join(skipped) + "."
        )

    if result.data_notes:
        lines.append("- Data notes: " + " ".join(result.data_notes))

    lines.append(
        "- "
        + _material_input_freshness_summary(
            result, default_as_of=result.as_of, regime_as_of=regime_as_of
        )
    )
    lines.append(f"- Data freshness: end-of-day, as of {result.as_of}.")
    lines.append(f"- {result.disclaimer}")
    if directive:
        lines.append(
            "- Scope: directive guidance here is for the single owner of this personal-use "
            "tool only; it is not advice for anyone else and must not be redistributed."
        )
    return "\n".join(lines)


def build_advisor_prompt(
    result: AnalyzeResponse,
    strategy: Strategy,
    *,
    survivorship: dict,
    regime: str | None = None,
    directive: bool = False,
) -> str:
    """Assemble the copy-ready advisor prompt for one candidate.

    Pure function of its inputs: contains no wall-clock time, so it is
    byte-identical on re-run for a fixed snapshot (FR-011). Sections follow
    contracts/advisor-prompt.schema.md; the honesty block is always last and
    always present.
    """
    gate_names = [g.gate for g in result.gate_results]
    sections = [
        _task_instruction(directive),
        _strategy_context(strategy, gate_names),
        _candidate_block(result, regime_as_of=result.as_of),
        _gate_breakdown(result),
        _regime_block(strategy, regime),
        _honesty_block(result, survivorship, directive, regime_as_of=result.as_of),
    ]
    return "\n\n".join(sections) + "\n"


# ---------------------------------------------------------------------------
# Batch (whole-screen) prompt
# ---------------------------------------------------------------------------


def _research_and_summary_instruction(directive: bool, *, multi: bool) -> str:
    """Appended research + presentation instructions (owner request): web-search
    news + analyst opinion, optionally compare across names, and close with a brief
    Arabic summary of the strongest candidates. News/analyst material is external
    context that NEVER overwrites a computed gate (Claude-Project rule #9). The
    'strongest' framing stays neutral when directive guidance is off (hosted mode
    forces it off and non-waivable)."""
    best = (
        "lists the ENTER names best-to-worst to act on now, with the WATCH names after"
        if directive
        else "highlights the ENTER-candidate names (strongest screen matches for further "
        "research), with the WATCH names after"
    )
    parts = [
        "ADDITIONAL RESEARCH (use web search; cite and DATE every source):",
        "(1) Search recent NEWS that could affect each stock over the 60-180 day horizon "
        "(earnings, guidance, M&A, regulatory, sector catalysts) and surface post-catalyst "
        "'news-exhaustion' pullback risk. News informs the RISK NARRATIVE only — it must never "
        "overwrite a computed gate result, and never read prices/fundamentals out of an article "
        "as if they were the screener's numbers.",
        "(2) Search current ANALYST opinion (ratings, price targets, recent revisions) and treat "
        "it as external opinion, clearly separate from the screener's own output.",
    ]
    if multi:
        parts.append(
            "(3) COMPARE the candidates against one another on setup quality, entry-timing state, "
            "reward:risk, and the news/analyst picture."
        )
    parts.append(
        "FINALLY, end with a BRIEF summary in ARABIC (فقرة موجزة بالعربية) that "
        f"{best}, one short reason each. Keep every citation and the honesty caveats "
        "(survivorship + data-tier) intact."
    )
    return "\n".join(parts)


_BUCKET_PREGATE = (
    "FIRST gate the WHOLE list before bucketing: confirm the market regime and "
    "(for Shariah-compliant screens) halal-source freshness from the context below. "
    "If the regime is Unfavorable or Unknown, or the compliance data is stale, say so "
    "and cap every name at WATCH until it is resolved."
)
_BUCKET_EXCLUDE = (
    "EXCLUDE from BOTH buckets (not merely demote) any candidate carrying a DATA "
    "INTEGRITY WARNING, a stale corporate-action / pinned-price signature, or marked "
    "data-suspect."
)
_BUCKET_ENTRY_TIMING_MOMENTUM = (
    "Treat the entry-timing state as a TIE-BREAKER / RISK-VETO, NOT a gate: a clean name "
    "that is below its pivot or shows a weak-volume breakout is still a valid ENTER (that "
    "is the George & Hwang underreaction-drift thesis) — entry-timing only DEMOTES the "
    "names that are materially extended above the 200-day SMA, or that fired a forcing "
    "disqualifier (climax-top, huge-gap) or a short-lived-catalyst caution. Show each "
    "name's 200-day-SMA distance and entry-timing state so the demotion is visible."
)
_BUCKET_RANK = (
    "RANK within each bucket: fewer soft-gate warnings first, then strategy score, then "
    "lower 200-day-SMA distance, then better fundamental coverage."
)


def _batch_task_instruction(directive: bool, n: int, *, is_momentum: bool) -> str:
    timing = (_BUCKET_ENTRY_TIMING_MOMENTUM + " ") if is_momentum else (
        "This strategy has NO entry-timing overlay — rank on the value composite, the "
        "Piotroski F-Score (and its evaluable count), and data coverage; never invent an "
        "entry-timing state for it. "
    )
    if directive:
        base = (
            "TASK (personal-use, single-user — directive guidance permitted): You are an "
            f"expert advisor for the strategy below. {n} candidate(s) passed the screen. Produce a "
            "READY ENTER / WATCH recommendation. "
            f"{_BUCKET_PREGATE} {_BUCKET_EXCLUDE} "
            "ENTER = passes all ESSENTIAL gates (a skipped PREFERRED gate is allowed but lowers "
            "rank), no forcing disqualifier, ranks high, and is not dangerously extended above its "
            "200-day SMA. WATCH = otherwise-clean names that ranked below the Enter cut, are "
            "materially extended, carry a short-lived-catalyst caution that needs a news check, or "
            f"are entry-undetermined from thin data. {timing}{_BUCKET_RANK} "
            "For each ENTER name give entry / stop / target and a risk-per-trade size (capped at "
            "the 10% position / 25% sector limits), with your confidence and the single biggest "
            "risk. Use only the numbers provided here — do not compute or invent figures. End with "
            "the honesty caveats. This guidance is for the single owner of this tool only and must "
            "not be redistributed."
        )
    else:
        base = (
            "TASK: You are an expert analyst for the strategy below. "
            f"{n} candidate(s) passed the screen. Classify the list into two research buckets — "
            "ENTER-candidate (setup-ready for the user's own entry consideration) and WATCH "
            "(await confirmation) — as screen matches / candidates for further research, not "
            f"recommendations. {_BUCKET_PREGATE} {_BUCKET_EXCLUDE} "
            "ENTER-candidate = passes all ESSENTIAL gates (a skipped PREFERRED gate is allowed but "
            "lowers rank), no forcing disqualifier, ranks high, and is not dangerously extended "
            "above its 200-day SMA. WATCH = otherwise. "
            f"{timing}{_BUCKET_RANK} Use only the numbers provided here — do not compute or invent "
            "figures. End with the honesty caveats."
        )
    return (
        base
        + " "
        + _EMBEDDED_SENTIMENT_NOTE
        + "\n\n"
        + _research_and_summary_instruction(directive, multi=True)
    )


# ---------------------------------------------------------------------------
# Embedded sentiment & narrative (feature 017) — a pure renderer that turns ONE
# already-captured SentimentReport into a labeled, clearly-separated, non-directive
# sub-block. Consumes ONLY content-addressed report fields (never `captured_at` or
# any wall-clock), so re-export is byte-identical (FR-007). Absent report ⇒ the
# caller appends nothing, keeping output byte-identical to today (FR-008).
# ---------------------------------------------------------------------------

_SENTIMENT_HEADING = (
    "### External context — sentiment & narrative (informational; does NOT change "
    "gates/levels)"
)

_NARRATIVE_SOURCE_LABEL = {
    NarrativeSource.MODEL: "model",
    NarrativeSource.TEMPLATE: "template",
    NarrativeSource.ABSENT: "absent",
}


def _sentiment_source_lines(report: SentimentReport) -> list[str]:
    present = ", ".join(report.source_classes_present) or "none"
    omitted = ", ".join(report.source_classes_omitted)
    header = f"- Sources ({present} present" + (
        f"; {omitted} omitted):" if omitted else "):"
    )
    lines = [header]
    # Most-recent first; verbatim third-party titles are quoted attributed material
    # (dated, deterministic), not app copy, so they are NOT run through the directive
    # lint — a publisher headline containing a banned word must not crash the export.
    for item in sorted(report.sources, key=lambda s: (s.published_at, s.id), reverse=True):
        publisher = item.publisher or item.source_class.value
        date = item.published_at.date().isoformat()
        stale = " [stale]" if item.is_stale else ""
        lines.append(f"  - {publisher}, {date}{stale} — {item.title}")
    return lines


def _sentiment_section(report: SentimentReport) -> str:
    """Render one captured `SentimentReport` as a non-directive prompt sub-block.

    Deterministic: never reads `captured_at`/wall-clock. The explicit no-signal /
    unavailable states print the report's stated status and fabricate NO narrative
    (FR-003). App-authored framing passes the no-directive lint (FR-006); verbatim
    source titles and the captured narrative (already lint-checked at capture) are
    quoted as-is."""
    lines = [_SENTIMENT_HEADING]

    no_signal = report.label == SentimentLabel.NO_SIGNAL or report.resolution in {
        "no_signal",
        "unavailable",
        "symbol_not_found",
    }
    if no_signal:
        status = report.label.value.replace("_", " ").upper()
        detail = report.resolution or report.label.value
        lines.append(
            f"- Sentiment status: {status} ({detail}) — no qualifying sourced "
            "sentiment was captured for this name; no narrative is provided."
        )
    else:
        label = report.label.value.replace("_", " ").upper()
        label_line = f"- Sentiment label: {label}"
        if report.label_basis:
            label_line += f" — {report.label_basis}"
        lines.append(label_line)

        if report.narrative:
            src = _NARRATIVE_SOURCE_LABEL.get(report.narrative_source, "source")
            lines.append(f"- Narrative ({src}): {report.narrative}")

        risk = report.narrative_risk
        if risk is not None:
            risk_line = f"- Narrative risk: {risk.score}/100 ({risk.label})"
            if risk.signals:
                risk_line += " — signals: " + "; ".join(risk.signals)
            lines.append(risk_line)

        if report.budget_state.value != "ok":
            lines.append(
                f"- Note: the paid narrative model was unavailable ({report.budget_state.value}); "
                "a deterministic source-only template was used."
            )

        lines.extend(_sentiment_source_lines(report))

    # Lint the app-authored framing only (headings/labels/notes/status), never the
    # verbatim third-party titles (indented source bullets) or the captured narrative
    # (already lint-checked at capture in feature 014).
    for line in lines:
        if line.startswith("  - ") or line.startswith("- Narrative ("):
            continue
        validate_no_directive_language(line)

    return "\n".join(lines)


def _candidate_summary_block(
    c,
    *,
    sector_gate_on: bool = False,
    material_freshness=None,
    default_as_of: str | None = None,
    sentiment: SentimentReport | None = None,
) -> str:
    """Compact per-candidate block for the batch prompt (operates on a Candidate)."""
    rr = _reward_risk(c.entry, c.stop_loss, c.take_profit)
    rank = getattr(c, "rank", None)
    head = f"### {f'#{rank} ' if rank is not None else ''}{c.ticker} — {c.name} ({c.sector})"
    levels = (
        f"- Current {c.current_price} | Entry {c.entry} | Stop {c.stop_loss}"
        + (f" (tighter {c.tighter_stop_loss})" if getattr(c, "tighter_stop_loss", None) else "")
        + f" | Target {c.take_profit}"
        + (f" | R:R {rr}" if rr else "")
    )
    lines = [head, levels]
    source = material_freshness or getattr(c, "material_input_freshness", None) or {}
    if source or default_as_of:
        freshness = _material_input_freshness_from_raw(
            source, default_as_of=default_as_of, regime_as_of=default_as_of
        )
        lines.append(
            "- "
            + (
                "Material input freshness: "
                f"prices {freshness['prices']}; "
                f"fundamentals {freshness['fundamentals']}; "
                f"regime {freshness['regime']}."
            )
        )
    if getattr(c, "data_integrity_warnings", []):
        for w in c.data_integrity_warnings:
            lines.append(f"### DATA INTEGRITY WARNING: {w.reason}")
    lines.extend(_diagnostics_lines(c))
    lines.extend(_entry_timing_lines(c))
    lines.extend(_skipped_gate_lines(c))
    gate_bits = []
    for g in c.gate_results:
        tag = {"pass": "PASS", "fail": "FAIL", "skipped": "SKIPPED"}.get(g.status, g.status.upper())
        gate_bits.append(f"{tag}:{g.gate}")
    if gate_bits:
        lines.append("- Gates: " + "; ".join(gate_bits))
    # A gate skipped on MISSING DATA is a genuine gap. The sector-strength gate
    # skipped because it is switched OFF this run is a configuration choice, not a
    # data gap (the Run configuration section explains it), so don't flag it here.
    skipped = [
        g.gate
        for g in c.gate_results
        if g.status == "skipped"
        and not (g.gate == "Sector strength" and not sector_gate_on)
    ]
    if skipped:
        lines.append(
            "- Data gaps (skipped, NOT real passes): " + ", ".join(skipped)
        )
    if sentiment is not None:
        lines.append(_sentiment_section(sentiment))
    return "\n".join(lines)


def _sector_gate_state(screen) -> tuple[bool, float | None]:
    """Resolve the sector-strength gate state for this run from the screen's
    parameter snapshot. Returns (on, fraction). on iff 0 < fraction < 1."""
    snap = getattr(screen, "parameters_snapshot", None) or {}
    raw = snap.get("sector_strength_top_fraction")
    try:
        frac = float(raw) if raw is not None else None
    except (TypeError, ValueError):
        frac = None
    return (frac is not None and 0.0 < frac < 1.0), frac


def _run_config_block(screen) -> str:
    """State the run's toggled configuration explicitly so the advisor doesn't have
    to infer it from gate statuses. Currently surfaces the sector-strength gate."""
    on, frac = _sector_gate_state(screen)
    lines = ["## Run configuration"]
    if on:
        pct = int(round(frac * 100))
        lines.append(
            f"- Sector-strength gate: ON — only candidates in the top {pct}% of sectors by "
            "breadth (fraction of members above their 200-day SMA) are kept; names in weaker "
            "sectors were filtered out BEFORE this list (Moskowitz & Grinblatt 1999, industry "
            "momentum). So every name below has already cleared sector strength."
        )
    else:
        lines.append(
            "- Sector-strength gate: OFF (default) — sector strength is NOT filtering this run. "
            "Any 'Sector strength: SKIPPED' below is by configuration, not missing data; do not "
            "treat it as a quality gap or penalize a name for it."
        )
    return "\n".join(lines)


def _batch_honesty_block(screen, survivorship: dict, directive: bool) -> str:
    lines = ["## Honesty & limitations (read before any performance judgment)"]
    if not survivorship.get("confirmed"):
        lines.append(
            "- Survivorship status: UNCONFIRMED — the backtest artifact was unavailable, "
            "so historical performance cannot be vouched for. Do not assume it is clean."
        )
    elif survivorship.get("passed") is False:
        note = survivorship.get("note") or ""
        lines.append(
            "- Survivorship bias: the backtest FAILS its survivorship check, so historical "
            "performance is OPTIMISTIC — delisted/failed companies are absent from the data."
            + (f" Detail: {note}" if note else "")
        )
    else:
        lines.append("- Survivorship bias: the backtest passes its survivorship check on this snapshot.")
    lines.append(
        "- Per-candidate data gaps (gates skipped on missing data) are flagged inline above "
        "and are NOT genuine passes."
    )
    if getattr(screen, "data_notes", None):
        lines.append("- Data notes: " + " ".join(screen.data_notes))
    if getattr(screen, "stale_sources", None):
        lines.append("- Stale sources: " + ", ".join(screen.stale_sources))
    lines.append(
        "- "
        + _material_input_freshness_summary(
            screen, default_as_of=screen.as_of_date, regime_as_of=screen.as_of_date
        )
    )
    lines.append(f"- Data freshness: end-of-day, as of {screen.as_of_date}.")
    lines.append(f"- {screen.disclaimer}")
    if directive:
        lines.append(
            "- Scope: directive guidance here is for the single owner of this personal-use "
            "tool only; it is not advice for anyone else and must not be redistributed."
        )
    return "\n".join(lines)


def _resolve_sentiment(
    sentiment_by_ticker: dict[str, SentimentReport] | None, ticker: str
) -> SentimentReport | None:
    """Case-insensitive lookup into the resolved sentiment mapping. Absent ⇒ None
    (the block builder then appends nothing, keeping output byte-identical)."""
    if not sentiment_by_ticker:
        return None
    return sentiment_by_ticker.get(ticker) or sentiment_by_ticker.get(
        str(ticker).strip().upper()
    )


def build_screen_advisor_prompt(
    screen,
    strategy: Strategy,
    *,
    survivorship: dict,
    directive: bool = False,
    sentiment_by_ticker: dict[str, SentimentReport] | None = None,
) -> str:
    """Assemble one combined advisor prompt covering every candidate in a screen.

    `screen` is a ScreenResult. Strategy context, regime, and the honesty block
    appear once; each candidate gets a compact block. Deterministic for a fixed
    snapshot (no wall-clock in the body). An optional `sentiment_by_ticker` mapping
    embeds each candidate's already-captured sentiment section; names without an
    entry are byte-identical to today (FR-008).
    """
    candidates = list(screen.candidates)
    gate_names = [g.gate for g in candidates[0].gate_results] if candidates else []
    sector_gate_on, _ = _sector_gate_state(screen)
    body = (
        "\n\n".join(
            _candidate_summary_block(
                c,
                sector_gate_on=sector_gate_on,
                material_freshness=getattr(screen, "material_input_freshness", None),
                default_as_of=screen.as_of_date,
                sentiment=_resolve_sentiment(sentiment_by_ticker, c.ticker),
            )
            for c in candidates
        )
        if candidates
        else "_No candidates matched the screen._"
    )
    sections = [
        _batch_task_instruction(
            directive,
            len(candidates),
            is_momentum=strategy.slug == "midterm_52w_high_momentum",
        ),
        _strategy_context(strategy, gate_names),
        _run_config_block(screen),
        "## Material input freshness\n"
        + "\n".join(
            _material_input_freshness_lines(
                screen, default_as_of=screen.as_of_date, regime_as_of=screen.as_of_date
            )
        ),
        _regime_block(strategy, getattr(screen, "regime", None)),
        f"## Candidates ({len(candidates)})\n{body}",
        _batch_honesty_block(screen, survivorship, directive),
    ]
    return "\n\n".join(sections) + "\n"


# ---------------------------------------------------------------------------
# Watchlist prompt (feature 017 US3) — a net-new prompt in the SAME screener-
# results format over the owner's watched names. Reuses the strategy-context,
# per-candidate block, sentiment section, and honesty machinery so the framing
# and determinism guarantees are identical to the screen export. The owner's
# watched names are re-evaluated against the strategy's CURRENT numbers (via
# `compute_candidate_result` in the API layer) — they are NOT asserted to have
# passed a screen. Pure function of its inputs (no wall-clock) → byte-identical
# re-export for a fixed snapshot + captured sentiment (FR-007/FR-014).
# ---------------------------------------------------------------------------


def _watchlist_task_instruction(directive: bool, n: int, *, is_momentum: bool) -> str:
    timing = (_BUCKET_ENTRY_TIMING_MOMENTUM + " ") if is_momentum else (
        "This strategy has NO entry-timing overlay — rank on the value composite, the "
        "Piotroski F-Score (and its evaluable count), and data coverage; never invent an "
        "entry-timing state for it. "
    )
    if directive:
        base = (
            "TASK (personal-use, single-user — directive guidance permitted): You are an "
            f"expert advisor for the strategy below. The owner is WATCHING {n} name(s) and wants "
            "each one re-evaluated against the strategy's CURRENT numbers (these are the owner's "
            "own watched names, not a fresh screen pass). Produce a READY ENTER / WATCH "
            f"recommendation. {_BUCKET_PREGATE} {_BUCKET_EXCLUDE} "
            "ENTER = passes all ESSENTIAL gates (a skipped PREFERRED gate is allowed but lowers "
            "rank), no forcing disqualifier, ranks high, and is not dangerously extended above its "
            "200-day SMA. WATCH = otherwise-clean names that ranked below the Enter cut, are "
            "materially extended, carry a short-lived-catalyst caution that needs a news check, or "
            f"are entry-undetermined from thin data. {timing}{_BUCKET_RANK} "
            "For each ENTER name give entry / stop / target and a risk-per-trade size (capped at "
            "the 10% position / 25% sector limits), with your confidence and the single biggest "
            "risk. Use only the numbers provided here — do not compute or invent figures. End with "
            "the honesty caveats. This guidance is for the single owner of this tool only and must "
            "not be redistributed."
        )
    else:
        base = (
            "TASK: You are an expert analyst for the strategy below. The owner is WATCHING "
            f"{n} name(s) and wants each one re-evaluated against the strategy's CURRENT numbers "
            "(these are the owner's own watched names, not a fresh screen pass). Classify the list "
            "into two research buckets — ENTER-candidate (setup-ready for the owner's own entry "
            "consideration) and WATCH (await confirmation) — as screen matches / candidates for "
            f"further research, not recommendations. {_BUCKET_PREGATE} {_BUCKET_EXCLUDE} "
            "ENTER-candidate = passes all ESSENTIAL gates (a skipped PREFERRED gate is allowed but "
            "lowers rank), no forcing disqualifier, ranks high, and is not dangerously extended "
            "above its 200-day SMA. WATCH = otherwise. "
            f"{timing}{_BUCKET_RANK} Use only the numbers provided here — do not compute or invent "
            "figures. End with the honesty caveats."
        )
    return (
        base
        + " "
        + _EMBEDDED_SENTIMENT_NOTE
        + "\n\n"
        + _research_and_summary_instruction(directive, multi=True)
    )


def _watchlist_unresolved_block(
    ticker: str, *, sentiment: SentimentReport | None = None
) -> str:
    """Render a watched name the current snapshot can't price/cover. It still
    appears (with an explicit no-coverage note) so the owner sees every watched
    name; its captured sentiment section is embedded only if one exists."""
    lines = [
        f"### {ticker}",
        "- Not priceable / no coverage on the current snapshot — this watched name is outside "
        "the screener's coverage universe, so no computed gate, price level, or size is available "
        "for it. Any external-context section below is dated sentiment only.",
    ]
    if sentiment is not None:
        lines.append(_sentiment_section(sentiment))
    return "\n".join(lines)


def _watchlist_honesty_block(
    results,
    survivorship: dict,
    directive: bool,
    *,
    data_as_of: str | None,
    disclaimer: str,
) -> str:
    """Shared honesty footer for the watchlist export. Mirrors the batch screen
    honesty block (survivorship + data-gap + freshness + disclaimer), aggregating
    the per-name data notes so it appears once."""
    lines = ["## Honesty & limitations (read before any performance judgment)"]
    if not survivorship.get("confirmed"):
        lines.append(
            "- Survivorship status: UNCONFIRMED — the backtest artifact was unavailable, "
            "so historical performance cannot be vouched for. Do not assume it is clean."
        )
    elif survivorship.get("passed") is False:
        note = survivorship.get("note") or ""
        lines.append(
            "- Survivorship bias: the backtest FAILS its survivorship check, so historical "
            "performance is OPTIMISTIC — delisted/failed companies are absent from the data."
            + (f" Detail: {note}" if note else "")
        )
    else:
        lines.append(
            "- Survivorship bias: the backtest passes its survivorship check on this snapshot."
        )
    lines.append(
        "- These are the owner's WATCHED names re-evaluated against the strategy's current "
        "numbers; being on the watchlist is not itself a screen pass or a recommendation."
    )
    lines.append(
        "- Per-candidate data gaps (gates skipped on missing data) are flagged inline above "
        "and are NOT genuine passes."
    )
    all_notes: list[str] = []
    for r in results:
        for n in getattr(r, "data_notes", None) or []:
            if n not in all_notes:
                all_notes.append(n)
    if all_notes:
        lines.append("- Data notes: " + " ".join(all_notes))
    as_of = _date_part(data_as_of) or "unavailable"
    freshness = _material_input_freshness_from_raw(
        {}, default_as_of=as_of, regime_as_of=as_of
    )
    lines.append(
        "- Material input freshness: "
        f"prices {freshness['prices']}; "
        f"fundamentals {freshness['fundamentals']}; "
        f"regime {freshness['regime']}."
    )
    lines.append(f"- Data freshness: end-of-day, as of {as_of}.")
    lines.append(f"- {disclaimer}")
    if directive:
        lines.append(
            "- Scope: directive guidance here is for the single owner of this personal-use "
            "tool only; it is not advice for anyone else and must not be redistributed."
        )
    return "\n".join(lines)


def build_watchlist_advisor_prompt(
    strategy: Strategy,
    results,
    *,
    survivorship: dict,
    gate_names: list[str] | None = None,
    regime: str | None = None,
    directive: bool = False,
    data_as_of: str | None = None,
    disclaimer: str = DISCLAIMER_TEXT,
    unresolved: list[str] | None = None,
    sentiment_by_ticker: dict[str, SentimentReport] | None = None,
) -> str:
    """Assemble ONE advisor prompt over the owner's watched names, in the SAME
    format as the screener-results export.

    `results` is a list of computed `AnalyzeResponse` objects (one per watched
    name the snapshot could price); `unresolved` lists watched tickers the
    snapshot could not price (they still appear, with a no-coverage note). The
    strategy declaration, regime, and honesty footer appear once; each name gets
    a compact block with its already-captured sentiment section embedded when a
    report exists (absent ⇒ byte-identical, FR-008). Pure function of its inputs
    (no wall-clock) → byte-identical re-export for a fixed snapshot (FR-007).
    """
    results = list(results)
    unresolved = list(unresolved or [])
    watched_count = len(results) + len(unresolved)
    if gate_names is None:
        gate_names = [g.gate for g in results[0].gate_results] if results else []

    blocks: list[str] = []
    for r in results:
        blocks.append(
            _candidate_summary_block(
                r,
                sector_gate_on=False,
                material_freshness=None,
                default_as_of=getattr(r, "as_of", None) or _date_part(data_as_of),
                sentiment=_resolve_sentiment(sentiment_by_ticker, r.ticker),
            )
        )
    for ticker in unresolved:
        blocks.append(
            _watchlist_unresolved_block(
                ticker, sentiment=_resolve_sentiment(sentiment_by_ticker, ticker)
            )
        )
    body = (
        "\n\n".join(blocks)
        if blocks
        else "_No watched names to evaluate. Add names to the watchlist to include them here._"
    )

    sections = [
        _watchlist_task_instruction(
            directive,
            watched_count,
            is_momentum=strategy.slug == "midterm_52w_high_momentum",
        ),
        _strategy_context(strategy, gate_names),
        _regime_block(strategy, regime),
        f"## Watched names ({watched_count})\n{body}",
        _watchlist_honesty_block(
            results,
            survivorship,
            directive,
            data_as_of=data_as_of,
            disclaimer=disclaimer,
        ),
    ]
    return "\n\n".join(sections) + "\n"


# ---------------------------------------------------------------------------
# Four-variant matrix prompt (feature 006) — one shared header + regime, four
# delimited variant sections, one combined honesty footer. Reuses the per-screen
# section builders so it inherits their determinism and directive gating.
# ---------------------------------------------------------------------------


def _matrix_task_instruction(directive: bool) -> str:
    if directive:
        return (
            "TASK (personal-use, single-user — directive guidance permitted): You are an "
            "expert advisor. Below are FOUR variants of two mid-term strategies, each toggling "
            "ONE gate on/off over the SAME universe snapshot. For each variant, walk its gates "
            "and give a concise directive call (take / pass / size) with your confidence; then "
            "compare the variants and say which configuration you would act on and why. Use only "
            "the numbers provided here — do not compute or invent figures. End with the honesty "
            "caveats. This guidance is for the single owner of this tool only and must not be "
            "redistributed."
        )
    return (
        "TASK: You are an expert analyst. Below are FOUR variants of two mid-term strategies, "
        "each toggling ONE gate on/off over the SAME universe snapshot. For each variant, explain "
        "neutrally how its candidates score against that strategy's rules, then compare the "
        "variants as screen configurations (screen matches / candidates for further research, not "
        "recommendations). Use only the numbers provided here — do not compute or invent figures. "
        "End with the honesty caveats."
    )


def _matrix_regime_block(regime: str | None) -> str:
    head = (
        f"- Current regime: {regime}"
        if regime
        else "- Current regime: unavailable for this snapshot (treat regime-dependent "
        "favorability as unknown)"
    )
    return (
        "## Market regime\n"
        f"{head}\n"
        "- (favorability is noted per-strategy inside each variant section)"
    )


def _variant_run_config(variant) -> str:
    """Run-configuration block for one variant, stating the toggled parameter's
    value explicitly (FR-012 item 2) and whether the gate is intentionally
    ON/OFF (FR-006). Momentum reuses the per-screen sector-gate block; value gets
    a momentum-floor description."""
    toggle_line = (
        f"- Toggle: {variant.toggle_param} = {variant.toggle_value} "
        f"({'ON' if variant.toggle_on else 'OFF'})"
    )
    if variant.toggle_param == "sector_strength_top_fraction":
        base = _run_config_block(variant.screen)
        head, _, rest = base.partition("\n")
        return f"{head}\n{toggle_line}\n{rest}"
    # Value momentum-floor toggle.
    lines = ["## Run configuration", toggle_line]
    if variant.toggle_on:
        pct = int(round(abs(variant.toggle_value) * 100))
        lines.append(
            f"- Momentum floor: ON — names whose 12-1 month price momentum is below -{pct}% are "
            "dropped (falling-knife guard); names with unknown momentum pass through. The "
            "Piotroski gate screens financial health, not price trend, so this adds a trend "
            "requirement on top of pure value."
        )
    else:
        lines.append(
            "- Momentum floor: OFF (pure value, default) — price trend is NOT filtering this run; "
            "the Piotroski F-Score screens financial health only, so deep decliners can pass. Any "
            "momentum-floor skip below is by configuration, not missing data; do not treat it as a "
            "quality gap."
        )
    return "\n".join(lines)


def _matrix_candidates_block(variant) -> str:
    candidates = list(variant.screen.candidates)
    sector_gate_on = (
        variant.toggle_param == "sector_strength_top_fraction" and variant.toggle_on
    )
    body = (
        "\n\n".join(
            _candidate_summary_block(c, sector_gate_on=sector_gate_on)
            if not getattr(variant.screen, "material_input_freshness", None)
            else _candidate_summary_block(
                c,
                sector_gate_on=sector_gate_on,
                material_freshness=variant.screen.material_input_freshness,
                default_as_of=variant.screen.as_of_date,
            )
            for c in candidates
        )
        if candidates
        else "_No candidates matched this variant._"
    )
    return f"### Candidates ({len(candidates)})\n{body}"


def _matrix_strategy_kind(slug: str) -> str:
    return "value" if slug == "midterm_value_composite" else "momentum"


def _matrix_bias_line(variant) -> str:
    kind = _matrix_strategy_kind(variant.strategy.slug)
    b = variant.bias_check or {}
    if not b.get("confirmed"):
        verdict = (
            "UNCONFIRMED — backtest artifact unavailable; do not assume it is clean"
        )
    elif b.get("passed") is False:
        note = b.get("note") or ""
        verdict = (
            "FAILS its survivorship check — historical performance is OPTIMISTIC "
            "(delisted/failed names absent)" + (f". {note}" if note else "")
        )
    else:
        verdict = "passes its survivorship check on this snapshot"
    return f"- Backtest bias-check ({kind}): {verdict}"


def _matrix_honesty_block(variants, directive: bool) -> str:
    screen0 = variants[0].screen
    lines = ["## Honesty & limitations (read before any performance judgment)"]
    # Per-strategy survivorship caveat, deduped, stated as applying to BOTH of a
    # strategy's variants (Decision 6). Insertion order is the fixed variant order
    # (momentum then value), so the footer is deterministic.
    seen: dict[str, tuple[str, dict]] = {}
    for v in variants:
        seen.setdefault(v.strategy.slug, (v.strategy.name, v.bias_check or {}))
    for _slug, (name, b) in seen.items():
        if not b.get("confirmed"):
            lines.append(
                f"- {name}: survivorship UNCONFIRMED (backtest artifact unavailable) — applies "
                "to BOTH of its variants above."
            )
        elif b.get("passed") is False:
            note = b.get("note") or ""
            lines.append(
                f"- {name}: backtest FAILS survivorship, so historical performance is OPTIMISTIC "
                "for BOTH of its variants above — a screen-time toggle does not re-run the "
                "backtest." + (f" Detail: {note}" if note else "")
            )
        else:
            lines.append(
                f"- {name}: backtest passes survivorship on this snapshot (applies to both of its "
                "variants)."
            )
    lines.append(
        "- Per-candidate data gaps (gates skipped on missing data) are flagged inline above and "
        "are NOT genuine passes."
    )
    notes: list[str] = []
    for v in variants:
        for n in v.screen.data_notes or []:
            if n not in notes:
                notes.append(n)
    if notes:
        lines.append("- Data notes: " + " ".join(notes))
    lines.append(
        "- "
        + _material_input_freshness_summary(
            screen0, default_as_of=screen0.as_of_date, regime_as_of=screen0.as_of_date
        )
    )
    lines.append(f"- Data freshness: end-of-day, as of {screen0.as_of_date}.")
    lines.append(f"- {screen0.disclaimer}")
    if directive:
        lines.append(
            "- Scope: directive guidance here is for the single owner of this personal-use tool "
            "only; it is not advice for anyone else and must not be redistributed."
        )
    return "\n".join(lines)


def build_midterm_matrix_advisor_prompt(
    variants,
    *,
    regime: str | None = None,
    directive: bool = False,
) -> str:
    """Assemble ONE advisor prompt covering all four mid-term variants.

    `variants` is a list of `VariantResult`. One shared task header + market
    regime, then four delimited variant sections (declaration + run-config +
    candidates + that strategy's bias-check), then one combined honesty footer.
    Pure function of its inputs (no wall-clock) → byte-identical re-export for a
    fixed snapshot (FR-013). Sections follow contracts/advisor-prompt.schema.md.
    """
    sections = [
        _matrix_task_instruction(directive),
        _matrix_regime_block(regime),
    ]
    for i, variant in enumerate(variants, start=1):
        gate_names = (
            [g.gate for g in variant.screen.candidates[0].gate_results]
            if variant.screen.candidates
            else []
        )
        sections.append(
            "\n\n".join(
                [
                    f"## Variant {i} — {variant.label}",
                    _strategy_context(variant.strategy, gate_names),
                    _variant_run_config(variant),
                    _matrix_candidates_block(variant),
                    _matrix_bias_line(variant),
                ]
            )
        )
    sections.append(_matrix_honesty_block(variants, directive))
    return "\n\n".join(sections) + "\n"


# ---------------------------------------------------------------------------
# Held-position prompt (feature 014) — a hold/trim/exit review of a position the
# owner ALREADY OWNS, built from the feature-013 holdings data (cost basis, both
# purchase-anchored level bases, and the risk-aware sizing view). Reuses the
# strategy-context, regime, and reward:risk helpers so the declaration + honesty
# framing stay the single source of truth. Pure (no wall-clock in the body).
# ---------------------------------------------------------------------------


def _fmt_money(value) -> str | None:
    if value is None:
        return None
    return f"{Decimal(str(value)):.2f}"


def _fmt_signed_pct(value) -> str | None:
    if value is None:
        return None
    return f"{value * 100:+.1f}%"


def _holding_task_instruction(directive: bool, *, multi: bool) -> str:
    scope = "these positions" if multi else "this position"
    if directive:
        base = (
            "TASK (personal-use, single-user — directive guidance permitted): You are an "
            f"expert advisor reviewing {scope} the user ALREADY HOLDS. For each holding, walk "
            "its purchase-anchored stop/target (both the original-plan and current-condition "
            "bases) and its capital-at-risk, judge whether the original strategy thesis still "
            "holds, and give a concrete directive call — HOLD, TRIM, or EXIT — with your "
            "confidence and the single biggest risk that would change it. Use only the numbers "
            "provided here — do not compute or invent figures. End with the honesty caveats. "
            "This guidance is for the single owner of this tool only and must not be redistributed."
        )
    else:
        base = (
            "TASK: You are an expert analyst reviewing "
            f"{scope} the user ALREADY HOLDS. For each holding, explain neutrally how it now "
            "scores against the strategy's rules and where it sits relative to its "
            "purchase-anchored stop/target (both the original-plan and current-condition bases) "
            "and its capital-at-risk. Discuss whether the original thesis still holds and lay out "
            "hold / trim / exit considerations as research for the user's own decision, not a "
            "recommendation. Use only the numbers provided here — do not compute or invent "
            "figures. End with the honesty caveats."
        )
    return (
        base
        + " "
        + _EMBEDDED_SENTIMENT_NOTE
        + "\n\n"
        + _research_and_summary_instruction(directive, multi=multi)
    )


def _level_base_lines(label: str, block, note: str) -> list[str]:
    lines = [f"### {label} levels ({note})"]
    if block is None or block.levels_state != "ok":
        lines.append(
            "- Insufficient data to derive bounded levels for this base"
            + (f": {block.rationale}" if block is not None and block.rationale else ".")
        )
        return lines
    levels = (
        f"- Entry (avg cost): {_fmt_money(block.entry)} | Stop: {_fmt_money(block.stop_loss)}"
        + (
            f" (tighter {_fmt_money(block.tighter_stop_loss)})"
            if block.tighter_stop_loss is not None
            else ""
        )
        + f" | Target: {_fmt_money(block.take_profit)}"
    )
    lines.append(levels)
    rr = _reward_risk(
        str(block.entry) if block.entry is not None else "",
        str(block.stop_loss) if block.stop_loss is not None else "",
        str(block.take_profit) if block.take_profit is not None else "",
    )
    if rr is not None:
        lines.append(f"- Reward:risk = {rr}")
    dist_stop = _fmt_signed_pct(block.distance_to_stop_pct)
    dist_target = _fmt_signed_pct(block.distance_to_target_pct)
    if dist_stop is not None or dist_target is not None:
        lines.append(
            "- Distance to stop: "
            + (dist_stop or "n/a")
            + " | Distance to target: "
            + (dist_target or "n/a")
        )
    lines.append(f"- Status: {block.status.replace('_', ' ').upper()}")
    if block.rationale:
        lines.append(f"- Rationale: {block.rationale}")
    return lines


def _risk_view_lines(risk) -> list[str]:
    if risk is None:
        return [
            "### Risk view",
            "- Unavailable for this holding (no current-condition stop on this snapshot).",
        ]
    lines = [
        "### Risk view",
        f"- Suggested size: {risk.recommended_shares} shares "
        f"({_fmt_money(risk.recommended_value)}) vs actual {risk.actual_shares} shares "
        f"({_fmt_money(risk.actual_value)})",
        f"- Capital at risk (to current-condition stop): {_fmt_money(risk.actual_capital_at_risk)} "
        f"({risk.actual_capital_at_risk_pct * 100:.1f}% of capital)",
        f"- Per-trade risk budget: {_fmt_money(risk.per_trade_risk_budget)}",
    ]
    if risk.over_risk:
        lines.append(
            "- Over budget: yes — binding constraint: "
            f"{risk.binding_constraint or 'unspecified'}"
        )
    else:
        lines.append("- Over budget: no")
    if risk.fail_open:
        lines.append(
            "- Note: a conviction modulator input was missing, so sizing fell back to the "
            "bounded risk-per-trade baseline (fail-open)."
        )
    if risk.sizing_reasoning:
        lines.append(f"- Sizing basis: {risk.sizing_reasoning}")
    return lines


def _holding_block(holding, *, sentiment: SentimentReport | None = None) -> str:
    lines = [
        f"## Held position — {holding.ticker} ({holding.sector})",
        f"- Net quantity: {holding.net_quantity}",
        f"- Average cost: {_fmt_money(holding.avg_cost)}",
        f"- Cost basis: {_fmt_money(holding.cost_basis)}",
        f"- First purchase: {holding.earliest_buy_date} | Latest purchase: {holding.most_recent_buy_date}",
        f"- Realized P/L: {_fmt_money(holding.realized_pl)}",
    ]
    if not getattr(holding, "priceable", False) or holding.current_price is None:
        lines.append(
            "- Current price: not priceable on the current snapshot — this ticker is outside "
            "the screener's coverage universe, so levels and risk cannot be derived. The "
            "cost-basis facts above are the owner's own records."
        )
        if getattr(holding, "data_notes", None):
            lines.append("- Data notes: " + " ".join(holding.data_notes))
        if sentiment is not None:
            lines.append(_sentiment_section(sentiment))
        return "\n".join(lines)

    price_line = f"- Current price: {_fmt_money(holding.current_price)}"
    if holding.data_as_of:
        price_line += f" (as of {_date_part(holding.data_as_of)})"
    lines.append(price_line)
    if holding.unrealized_pl is not None:
        upl = f"- Unrealized P/L: {_fmt_money(holding.unrealized_pl)}"
        if holding.unrealized_pl_pct is not None:
            upl += f" ({_fmt_signed_pct(holding.unrealized_pl_pct)})"
        lines.append(upl)

    levels = holding.levels
    lines.extend(
        _level_base_lines(
            "Original-plan",
            levels.original_plan if levels else None,
            "anchored to average cost, volatility as of the earliest purchase date",
        )
    )
    lines.extend(
        _level_base_lines(
            "Current-condition",
            levels.current_condition if levels else None,
            "anchored to average cost, latest-snapshot volatility",
        )
    )
    lines.extend(_risk_view_lines(holding.risk))
    if getattr(holding, "data_notes", None):
        lines.append("- Data notes: " + " ".join(holding.data_notes))
    if sentiment is not None:
        lines.append(_sentiment_section(sentiment))
    return "\n".join(lines)


def _holding_honesty_block(
    survivorship: dict,
    directive: bool,
    *,
    data_as_of: str | None,
    disclaimer: str,
    data_notes: list[str] | None = None,
) -> str:
    lines = ["## Honesty & limitations (read before any performance judgment)"]
    if not survivorship.get("confirmed"):
        lines.append(
            "- Survivorship status: UNCONFIRMED — the backtest artifact was unavailable, "
            "so historical performance cannot be vouched for. Do not assume it is clean."
        )
    elif survivorship.get("passed") is False:
        note = survivorship.get("note") or ""
        lines.append(
            "- Survivorship bias: the backtest FAILS its survivorship check, so historical "
            "performance (hit-rate, returns) is OPTIMISTIC — delisted/failed companies are "
            "absent from the data." + (f" Detail: {note}" if note else "")
        )
    else:
        lines.append(
            "- Survivorship bias: the backtest passes its survivorship check on this snapshot."
        )
    lines.append(
        "- Levels are anchored to the owner's average cost (a real fill), not a fresh entry; "
        "the current-condition base re-derives volatility on the latest snapshot. Sizing is the "
        "risk-per-trade backbone, hard-bounded by the position/sector caps."
    )
    if data_notes:
        lines.append("- Data notes: " + " ".join(data_notes))
    lines.append(f"- Data freshness: end-of-day, as of {_date_part(data_as_of) or 'unavailable'}.")
    lines.append(f"- {disclaimer}")
    if directive:
        lines.append(
            "- Scope: directive guidance here is for the single owner of this personal-use "
            "tool only; it is not advice for anyone else and must not be redistributed."
        )
    return "\n".join(lines)


def build_holding_advisor_prompt(
    holding,
    strategy: Strategy,
    *,
    survivorship: dict,
    regime: str | None = None,
    directive: bool = False,
    sentiment: SentimentReport | None = None,
) -> str:
    """Assemble the copy-ready hold/trim/exit review prompt for one held position.

    Pure function of its inputs (no wall-clock in the body), so it is byte-identical
    on re-run for a fixed snapshot + portfolio. The honesty block is always last.
    An optional captured `sentiment` report embeds the section; absent ⇒ byte-identical
    to today (FR-008).
    """
    sections = [
        _holding_task_instruction(directive, multi=False),
        _strategy_context(strategy, []),
        _regime_block(strategy, regime),
        _holding_block(holding, sentiment=sentiment),
        _holding_honesty_block(
            survivorship,
            directive,
            data_as_of=getattr(holding, "data_as_of", None),
            disclaimer=holding.disclaimer if hasattr(holding, "disclaimer") else DISCLAIMER_TEXT,
            data_notes=getattr(holding, "data_notes", None),
        ),
    ]
    return "\n\n".join(sections) + "\n"


def build_portfolio_advisor_prompt(
    holdings,
    totals,
    strategy: Strategy,
    *,
    survivorship: dict,
    regime: str | None = None,
    directive: bool = False,
    sentiment_by_ticker: dict[str, SentimentReport] | None = None,
) -> str:
    """Assemble ONE hold/trim/exit review prompt covering every held position.

    Strategy context, regime, totals, and the honesty block appear once; each
    holding gets its own block. Pure function of its inputs (no wall-clock) →
    byte-identical re-export for a fixed snapshot + portfolio. An optional
    `sentiment_by_ticker` mapping embeds each holding's already-captured sentiment
    section; holdings without an entry are byte-identical to today (FR-008).
    """
    holdings = list(holdings)
    body = (
        "\n\n".join(
            _holding_block(h, sentiment=_resolve_sentiment(sentiment_by_ticker, h.ticker))
            for h in holdings
        )
        if holdings
        else "_No open holdings._"
    )
    totals_line = (
        "## Portfolio totals\n"
        f"- Total invested: {_fmt_money(totals.total_invested)}\n"
        f"- Total capital at risk: {_fmt_money(totals.total_capital_at_risk)} "
        f"({totals.total_capital_at_risk_pct * 100:.1f}% of capital)"
    )
    newest_as_of = max(
        (h.data_as_of for h in holdings if getattr(h, "data_as_of", None)),
        default=None,
    )
    all_notes: list[str] = []
    for h in holdings:
        for n in getattr(h, "data_notes", None) or []:
            if n not in all_notes:
                all_notes.append(n)
    sections = [
        _holding_task_instruction(directive, multi=True),
        _strategy_context(strategy, []),
        _regime_block(strategy, regime),
        totals_line,
        f"## Holdings ({len(holdings)})\n{body}",
        _holding_honesty_block(
            survivorship,
            directive,
            data_as_of=newest_as_of,
            disclaimer=DISCLAIMER_TEXT,
            data_notes=all_notes,
        ),
    ]
    return "\n\n".join(sections) + "\n"
