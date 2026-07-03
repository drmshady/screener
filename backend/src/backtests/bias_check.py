from __future__ import annotations


def build_bias_check(
    source_name: str,
    uses_point_in_time_fundamentals: bool,
    delisted_coverage: bool = False,
    uses_fundamentals: bool = True,
    cost_bps: float = 0.0,
) -> dict:
    if delisted_coverage and source_name == "stooq":
        survivorship_note = "Stooq deep history with delisted-ticker coverage; survivor-bias-free."
    elif source_name == "stooq":
        survivorship_note = (
            "Stooq deep-history bundle used (full live universe, 2008-2009 covered), but the "
            "free bundle contains NO delisted tickers — survivor-bias-free coverage requires a "
            "delisted source (e.g., EOD Historical Data)."
        )
    else:
        survivorship_note = "Run used yfinance for currently listed tickers only; survivor-bias-free coverage is not proven."
    return {
        "survivorship_bias": {
            "passed": delisted_coverage and source_name == "stooq",
            "note": survivorship_note,
        },
        "lookahead_bias": {
            "passed": True,
            "note": "Candidate selection uses prices at or before each rebalance as-of date.",
        },
        "point_in_time_fundamentals": {
            "passed": (not uses_fundamentals) or uses_point_in_time_fundamentals,
            "note": (
                "No fundamentals are used by this strategy; price signals are evaluated only from bars visible at the rebalance date."
                if not uses_fundamentals
                else (
                    "Point-in-time fundamentals were available."
                    if uses_point_in_time_fundamentals
                    else "Quality gate used current provider fundamentals; this is not a constitution-grade fundamentals backtest."
                )
            ),
        },
        "costs": {
            "passed": cost_bps > 0,
            "note": (
                f"modeled: {cost_bps:g} bps/side"
                if cost_bps > 0
                else "No transaction costs modeled (0 bps/side)."
            ),
        },
    }


def to_markdown(strategy_slug: str, start: str, end: str, bias_check: dict) -> str:
    lines = [f"# Bias Check: {strategy_slug}", "", f"Window: {start} to {end}.", ""]
    for item, details in bias_check.items():
        mark = "x" if details["passed"] else " "
        lines.append(f"- [{mark}] {item}: {details['note']}")
    lines.append("")
    return "\n".join(lines)
