from __future__ import annotations

import json
from pathlib import Path

from ..models.strategy import AnalyzeResponse, Strategy

# ---------------------------------------------------------------------------
# Input gatherers (read-only; no recomputation of any candidate figure)
# ---------------------------------------------------------------------------

_BACKTEST_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "backtests"
    / "midterm_52w_high_momentum.json"
)


def load_survivorship_status(path: Path | None = None) -> dict:
    """Read the backtest artifact's survivorship-bias status.

    Returns ``{"confirmed": bool, "passed": bool | None, "note": str}``. When the
    artifact is missing/unreadable, ``confirmed`` is False and the honesty block
    states the status is unconfirmed (it never implies the backtest is clean).
    """
    p = path or _BACKTEST_PATH
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

    fund_bits: list[str] = []
    if getattr(c, "debt_to_equity", None) is not None:
        fund_bits.append(f"D/E {_fmt_num(c.debt_to_equity)}")
    if getattr(c, "fcf_ttm", None) is not None:
        fund_bits.append(f"FCF_ttm {_fmt_num(c.fcf_ttm)}")
    if getattr(c, "gp_to_assets", None) is not None:
        fund_bits.append(f"gp/assets {_fmt_num(c.gp_to_assets)}")
    if getattr(c, "asset_growth", None) is not None:
        fund_bits.append(f"asset_growth {_fmt_num(c.asset_growth, pct=True)}")
    if getattr(c, "atr", None) is not None:
        fund_bits.append(f"ATR {_fmt_num(c.atr)}")

    lines: list[str] = []
    if rank_bits:
        lines.append("- Ranking inputs: " + " | ".join(rank_bits))
    if fund_bits:
        lines.append("- Fundamentals: " + " | ".join(fund_bits))
    return lines


def _task_instruction(directive: bool) -> str:
    if directive:
        return (
            "TASK (personal-use, single-user — directive guidance permitted): You are an "
            "expert advisor for the strategy below. Walk the gate results in order, derive/"
            "confirm the entry, stop, and take-profit, then give a concrete directive call "
            "(take / pass / size) with your explicit confidence and the single biggest risk "
            "that would change it. Use only the numbers provided here — do not compute or "
            "invent figures. End with the honesty caveats. This guidance is for the single "
            "owner of this tool only and must not be redistributed."
        )
    return (
        "TASK: You are an expert analyst for the strategy below. Walk the gate results in "
        "order and explain neutrally how this name scores against the strategy's rules "
        "(treat it as a screen match / candidate for further research, not a recommendation). "
        "Use only the numbers provided here — do not compute or invent figures. End with the "
        "honesty caveats."
    )


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
    lines.append(
        "- Ranking: survivors are scored by return_12_1 × vol_scalar / (1 + dist_to_high) "
        f"(higher = stronger), then kept to at most {max_per_sector} per sector "
        "(sector-relative ranking). Any names beyond a sector's cap were dropped before this list."
    )
    lines.append("- Modifications (each with its own source):")
    for mod in strategy.modifications:
        lines.append(f"  - {mod.name} — {mod.description} [{mod.citation}]")
    return "\n".join(lines)


def _candidate_block(result: AnalyzeResponse) -> str:
    rr = _reward_risk(result.entry, result.stop_loss, result.take_profit)
    lines = [
        "## Candidate result",
        f"- Ticker: {result.ticker} — {result.name} ({result.sector})",
        f"- Data as of: {result.as_of}",
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
    if rr is not None:
        lines.append(f"- Reward:risk = {rr}")
    lines.extend(_diagnostics_lines(result))
    return "\n".join(lines)


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


def _honesty_block(result: AnalyzeResponse, survivorship: dict, directive: bool) -> str:
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
        _candidate_block(result),
        _gate_breakdown(result),
        _regime_block(strategy, regime),
        _honesty_block(result, survivorship, directive),
    ]
    return "\n\n".join(sections) + "\n"


# ---------------------------------------------------------------------------
# Batch (whole-screen) prompt
# ---------------------------------------------------------------------------


def _batch_task_instruction(directive: bool, n: int) -> str:
    if directive:
        return (
            "TASK (personal-use, single-user — directive guidance permitted): You are an "
            f"expert advisor for the strategy below. {n} candidate(s) passed the screen. For "
            "each, walk its gates and give a concise directive call (take / pass / size) with "
            "your confidence; then RANK them best-to-worst for opening a new position now and "
            "flag any you would avoid and why. Use only the numbers provided here — do not "
            "compute or invent figures. End with the honesty caveats. This guidance is for the "
            "single owner of this tool only and must not be redistributed."
        )
    return (
        "TASK: You are an expert analyst for the strategy below. "
        f"{n} candidate(s) passed the screen. For each, explain neutrally how it scores against "
        "the strategy's rules, then compare them as screen matches / candidates for further "
        "research (not recommendations). Use only the numbers provided here — do not compute or "
        "invent figures. End with the honesty caveats."
    )


def _candidate_summary_block(c) -> str:
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
    lines.extend(_diagnostics_lines(c))
    gate_bits = []
    for g in c.gate_results:
        tag = {"pass": "PASS", "fail": "FAIL", "skipped": "SKIPPED"}.get(g.status, g.status.upper())
        gate_bits.append(f"{tag}:{g.gate}")
    if gate_bits:
        lines.append("- Gates: " + "; ".join(gate_bits))
    skipped = [g.gate for g in c.gate_results if g.status == "skipped"]
    if skipped:
        lines.append(
            "- Data gaps (skipped, NOT real passes): " + ", ".join(skipped)
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
    lines.append(f"- Data freshness: end-of-day, as of {screen.as_of_date}.")
    lines.append(f"- {screen.disclaimer}")
    if directive:
        lines.append(
            "- Scope: directive guidance here is for the single owner of this personal-use "
            "tool only; it is not advice for anyone else and must not be redistributed."
        )
    return "\n".join(lines)


def build_screen_advisor_prompt(
    screen,
    strategy: Strategy,
    *,
    survivorship: dict,
    directive: bool = False,
) -> str:
    """Assemble one combined advisor prompt covering every candidate in a screen.

    `screen` is a ScreenResult. Strategy context, regime, and the honesty block
    appear once; each candidate gets a compact block. Deterministic for a fixed
    snapshot (no wall-clock in the body).
    """
    candidates = list(screen.candidates)
    gate_names = [g.gate for g in candidates[0].gate_results] if candidates else []
    body = (
        "\n\n".join(_candidate_summary_block(c) for c in candidates)
        if candidates
        else "_No candidates matched the screen._"
    )
    sections = [
        _batch_task_instruction(directive, len(candidates)),
        _strategy_context(strategy, gate_names),
        _regime_block(strategy, getattr(screen, "regime", None)),
        f"## Candidates ({len(candidates)})\n{body}",
        _batch_honesty_block(screen, survivorship, directive),
    ]
    return "\n\n".join(sections) + "\n"
