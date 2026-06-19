from __future__ import annotations

import json
from pathlib import Path

from ..models.strategy import AnalyzeResponse, Strategy

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


def _candidate_summary_block(
    c,
    *,
    sector_gate_on: bool = False,
    material_freshness=None,
    default_as_of: str | None = None,
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
    sector_gate_on, _ = _sector_gate_state(screen)
    body = (
        "\n\n".join(
            _candidate_summary_block(
                c,
                sector_gate_on=sector_gate_on,
                material_freshness=getattr(screen, "material_input_freshness", None),
                default_as_of=screen.as_of_date,
            )
            for c in candidates
        )
        if candidates
        else "_No candidates matched the screen._"
    )
    sections = [
        _batch_task_instruction(directive, len(candidates)),
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
