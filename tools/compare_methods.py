"""Deterministic FR-019 method-comparison harness for feature 011.

The harness emits a regenerable JSON report with the sections required by
`contracts/method-comparison.md`. The default path is intentionally fast and
offline: it evaluates stable frozen sample candidates so CI can prove byte-stable
generation and shipped-default drift detection. The CLI surface (`--snapshot`) is
kept stable for later expansion to a larger frozen snapshot.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.src.backtests.runner import _forward_return, _modeled_exit_return  # noqa: E402
from backend.src.lib import flags  # noqa: E402
from backend.src.models.portfolio import PortfolioCaps, SizingRequest  # noqa: E402
from backend.src.portfolio.sizing import size_position  # noqa: E402

ARTIFACT_DIR = ROOT / "backend" / "data" / "method_comparison"

# Fixed reference capital for the deterministic sizing head-to-head (the absolute
# dollars cancel out of the comparison; only relative size differences matter).
_SIZING_CAPITAL = Decimal("100000")
_CONVICTION_ENV = "SCREENER_SIZING_CONVICTION_SIGNAL"
_MODULATORS = ("none", "fair_value", "inverse_vol", "strategy_rank")

# Deterministic forward-price fixture for the OFFLINE backtest-delta mechanics
# check (no real bars in the frozen sample). Each path is run through the REAL
# runner exit functions (`_forward_return` vs `_modeled_exit_return`), so the
# delta responds to the level rules and exit logic instead of being a constant.
# The paths deliberately encode the two classic ways modeled exits underperform a
# fixed horizon — stopping out a name that later recovers (AAA) and capping a
# winner that runs further (BBB) — so the fixture reproduces improvement = False.
# This is a mechanics/regression check only; the re-baseline gate still requires
# improvement on a REAL snapshot (a candidate may carry a `forward_bars` list).
_BACKTEST_AS_OF = date(2026, 1, 31)
_BACKTEST_HORIZON_DAYS = 10
_BACKTEST_FIXTURE: dict[str, list[dict[str, Any]]] = {
    "AAA": [  # entry 100: dips to the 94 stop, then recovers well above by horizon
        {"as_of_date": "2026-02-02", "open": 100, "high": 101, "low": 99, "close": 100},
        {"as_of_date": "2026-02-03", "open": 99, "high": 100, "low": 93, "close": 96},
        {"as_of_date": "2026-02-04", "open": 98, "high": 110, "low": 97, "close": 108},
        {"as_of_date": "2026-02-05", "open": 108, "high": 122, "low": 107, "close": 120},
    ],
    "BBB": [  # entry 50: tags the 66 target early, then keeps running to 80
        {"as_of_date": "2026-02-02", "open": 50, "high": 51, "low": 49, "close": 50},
        {"as_of_date": "2026-02-03", "open": 51, "high": 67, "low": 50, "close": 64},
        {"as_of_date": "2026-02-04", "open": 64, "high": 82, "low": 63, "close": 80},
    ],
    "CCC": [  # entry 30: chops sideways, neither stop nor target touched
        {"as_of_date": "2026-02-02", "open": 30, "high": 31, "low": 29, "close": 30},
        {"as_of_date": "2026-02-03", "open": 30, "high": 32, "low": 28, "close": 31},
        {"as_of_date": "2026-02-04", "open": 31, "high": 33, "low": 28, "close": 30},
    ],
}

SELECTED_DEFAULT = {
    "risk_distance_atr_lo": 1.0,
    "risk_distance_atr_hi": 4.0,
    "reward_ceiling_z": 2.5,
    "reward_ceiling_use_fair_value": False,
    "take_profit_r_multiple": 3.0,
    "fair_value_basis": "intrinsic_model",
    "risk_per_trade_fraction": 0.01,
    "sizing_conviction_signal": "none",
    "sizing_inverse_vol_baseline": 0.02,
}

FROZEN_SAMPLE = [
    {
        "ticker": "AAA",
        "entry": 100.0,
        "stop_loss": 94.0,
        "take_profit": 114.0,
        "atr": 2.0,
        "fair_value": 118.0,
        "fair_value_trust_flag": "trusted",
        "suggested_shares": 166,
        "cap_bound": False,
    },
    {
        "ticker": "BBB",
        "entry": 50.0,
        "stop_loss": 42.0,
        "take_profit": 66.0,
        "atr": 2.5,
        "fair_value": None,
        "fair_value_trust_flag": "unavailable",
        "suggested_shares": 125,
        "cap_bound": False,
    },
    {
        "ticker": "CCC",
        "entry": 30.0,
        "stop_loss": 27.0,
        "take_profit": 37.5,
        "atr": 1.0,
        "fair_value": 29.0,
        "fair_value_trust_flag": "out_of_range",
        "suggested_shares": 333,
        "cap_bound": True,
    },
]


@dataclass(frozen=True)
class ShippedDefaults:
    risk_distance_atr_lo: float
    risk_distance_atr_hi: float
    reward_ceiling_z: float
    reward_ceiling_use_fair_value: bool
    fair_value_basis: str
    risk_per_trade_fraction: float
    sizing_conviction_signal: str
    sizing_inverse_vol_baseline: float


def current_shipped_defaults() -> dict[str, Any]:
    return asdict(
        ShippedDefaults(
            risk_distance_atr_lo=flags.risk_distance_atr_lo(),
            risk_distance_atr_hi=flags.risk_distance_atr_hi(),
            reward_ceiling_z=flags.reward_ceiling_z(),
            reward_ceiling_use_fair_value=flags.reward_ceiling_use_fair_value(),
            fair_value_basis=flags.fair_value_basis(),
            risk_per_trade_fraction=flags.risk_per_trade_fraction(),
            sizing_conviction_signal=flags.sizing_conviction_signal(),
            sizing_inverse_vol_baseline=flags.sizing_inverse_vol_baseline(),
        )
    )


def _round(value: float) -> float:
    return round(float(value), 6)


def _load_candidates(snapshot: str) -> list[dict[str, Any]]:
    path = Path(snapshot)
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [dict(row) for row in payload]
        if isinstance(payload, dict) and isinstance(payload.get("candidates"), list):
            return [dict(row) for row in payload["candidates"]]
    return [dict(row) for row in FROZEN_SAMPLE]


def _realism_metrics(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    ok = []
    over_ceiling = 0
    for row in candidates:
        entry = float(row["entry"])
        stop = float(row["stop_loss"])
        target = float(row["take_profit"])
        atr = float(row["atr"])
        valid = 0 < stop < entry < target and atr > 0
        if valid:
            risk = entry - stop
            reward = target - entry
            ok.append(
                {
                    "risk_to_atr": _round(risk / atr),
                    "reward_to_atr": _round(reward / atr),
                    "risk_to_price": _round(risk / entry),
                    "reward_to_price": _round(reward / entry),
                }
            )
            if reward > SELECTED_DEFAULT["reward_ceiling_z"] * atr * (180**0.5):
                over_ceiling += 1
    count = len(candidates)
    return {
        "candidate_count": count,
        "degenerate_rate": _round(1 - (len(ok) / count)) if count else 0.0,
        "over_ceiling_count": over_ceiling,
        "risk_to_atr": sorted(row["risk_to_atr"] for row in ok),
        "reward_to_atr": sorted(row["reward_to_atr"] for row in ok),
        "risk_to_price": sorted(row["risk_to_price"] for row in ok),
        "reward_to_price": sorted(row["reward_to_price"] for row in ok),
    }


def _coverage_metrics(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(candidates)
    trusted = sum(1 for row in candidates if row.get("fair_value_trust_flag") == "trusted")
    available = sum(1 for row in candidates if row.get("fair_value") is not None)
    return {
        "fair_value_available_rate": _round(available / count) if count else 0.0,
        "fair_value_trusted_rate": _round(trusted / count) if count else 0.0,
    }


def _size_under(candidates: list[dict[str, Any]], signal: str) -> list[dict[str, Any]]:
    """Size every candidate through the REAL `size_position` under one conviction
    modulator. Restores the prior env so the report stays deterministic and the
    process-wide default is untouched."""
    previous = os.environ.get(_CONVICTION_ENV)
    os.environ[_CONVICTION_ENV] = signal
    try:
        out: list[dict[str, Any]] = []
        for index, row in enumerate(candidates):
            entry = float(row["entry"])
            stop = float(row["stop_loss"])
            if not (0 < stop < entry):
                continue
            atr = row.get("atr")
            resp = size_position(
                SizingRequest(
                    candidate_ticker=str(row["ticker"]),
                    entry=Decimal(str(entry)),
                    total_capital=_SIZING_CAPITAL,
                    caps=PortfolioCaps(),
                    stop_loss=Decimal(str(stop)),
                    fair_value=(
                        Decimal(str(row["fair_value"]))
                        if row.get("fair_value") is not None
                        else None
                    ),
                    fair_value_trust_flag=row.get("fair_value_trust_flag"),
                    volatility=(float(atr) / entry) if atr else None,
                    strategy_rank=index + 1,  # frozen sort order = rank
                )
            )
            cap_bound = resp.binding_constraint in {"position_cap", "sector_cap"} or not resp.caps_respected
            out.append(
                {
                    "risk_per_share": entry - stop,
                    "shares": int(resp.suggested_shares),
                    "cap_bound": bool(cap_bound),
                    "conviction_used": bool(resp.conviction_used),
                    "adjustment": resp.conviction_adjustment,
                }
            )
        return out
    finally:
        if previous is None:
            os.environ.pop(_CONVICTION_ENV, None)
        else:
            os.environ[_CONVICTION_ENV] = previous


def _monotonicity(base_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Wider stop -> not-larger size, on the risk-per-trade backbone. Cap-bound
    rows are excluded (the cap, not the risk target, decides their size). Computed
    from real `size_position` output rather than asserted."""
    free = sorted(
        (r for r in base_rows if not r["cap_bound"]),
        key=lambda r: (r["risk_per_share"], -r["shares"]),
    )
    if len(free) < 2:
        return {"status": "insufficient_data", "evaluated": len(free), "violations": 0}
    violations = sum(
        1 for a, b in zip(free, free[1:])
        if b["risk_per_share"] > a["risk_per_share"] and b["shares"] > a["shares"]
    )
    return {
        "status": "pass" if violations == 0 else "fail",
        "evaluated": len(free),
        "violations": violations,
    }


def _sizing_metrics(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    head_to_head: dict[str, Any] = {}
    base_rows: list[dict[str, Any]] = []
    for signal in _MODULATORS:
        rows = _size_under(candidates, signal)
        if signal == "none":
            base_rows = rows
        shares = [r["shares"] for r in rows]
        head_to_head[signal] = {
            "sized": len(rows),
            "share_min": min(shares) if shares else 0,
            "share_max": max(shares) if shares else 0,
            "modulated": sum(1 for r in rows if r["conviction_used"]),
            "boosted": sum(1 for r in rows if r["adjustment"] == "boost"),
            "shrunk": sum(1 for r in rows if r["adjustment"] == "cap"),
        }
    cap_bound = sum(1 for r in base_rows if r["cap_bound"])
    base_shares = [r["shares"] for r in base_rows]
    return {
        "candidate_modulators": list(_MODULATORS),
        "selected_modulator": SELECTED_DEFAULT["sizing_conviction_signal"],
        "share_min": min(base_shares) if base_shares else 0,
        "share_max": max(base_shares) if base_shares else 0,
        "cap_bind_rate": _round(cap_bound / len(base_rows)) if base_rows else 0.0,
        "wider_stop_smaller_monotonicity": _monotonicity(base_rows),
        "conviction_head_to_head": head_to_head,
    }


def _bars_for(row: dict[str, Any]) -> tuple[list[dict[str, Any]], date, int, bool]:
    """Forward OHLC bars for one candidate's backtest leg: real bars when the
    snapshot supplies them (`forward_bars` + optional `as_of`/`horizon_days`),
    else the deterministic offline fixture keyed by ticker."""
    if isinstance(row.get("forward_bars"), list) and row["forward_bars"]:
        as_of = date.fromisoformat(row["as_of"]) if row.get("as_of") else _BACKTEST_AS_OF
        horizon = int(row.get("horizon_days", _BACKTEST_HORIZON_DAYS))
        return list(row["forward_bars"]), as_of, horizon, True
    return _BACKTEST_FIXTURE.get(str(row["ticker"]), []), _BACKTEST_AS_OF, _BACKTEST_HORIZON_DAYS, False


def _leg_returns(row: dict[str, Any]) -> tuple[float | None, float | None, bool]:
    bars, as_of, horizon, real = _bars_for(row)
    if not bars:
        return None, None, real
    ticker = str(row["ticker"])
    frame = pd.DataFrame(bars)
    frame["ticker"] = ticker
    frame["as_of_date"] = pd.to_datetime(frame["as_of_date"])
    by_ticker = frame.groupby("ticker", sort=False)
    fixed = _forward_return(by_ticker, ticker, as_of, horizon_days=horizon)
    modeled = _modeled_exit_return(
        by_ticker,
        ticker,
        as_of,
        stop_loss=float(row["stop_loss"]),
        take_profit=float(row["take_profit"]),
        horizon_days=horizon,
    )
    return fixed, modeled, real


def _backtest_delta(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Real level-driven modeled-exit delta: the runner's own `_forward_return`
    (fixed horizon, baseline) vs `_modeled_exit_return` (level-driven) averaged
    across the candidates that have forward bars. Deterministic; computed, not
    constant. Re-baseline stays gated on REAL-snapshot improvement."""
    fixed_returns: list[float] = []
    modeled_returns: list[float] = []
    any_real = False
    for row in candidates:
        fixed, modeled, real = _leg_returns(row)
        any_real = any_real or real
        if fixed is not None and modeled is not None:
            fixed_returns.append(fixed)
            modeled_returns.append(modeled)
    evaluated = len(fixed_returns)
    fixed_total = sum(fixed_returns) / evaluated if evaluated else 0.0
    modeled_total = sum(modeled_returns) / evaluated if evaluated else 0.0
    basis = "real_bars" if any_real else "synthetic_fixture_mechanics_check"
    improvement = evaluated > 0 and modeled_total > fixed_total
    return {
        "baseline_exit_model": "fixed_horizon",
        "candidate_exit_model": "modeled_levels",
        "basis": basis,
        "candidates_evaluated": evaluated,
        "fixed_total_return": _round(fixed_total),
        "modeled_total_return": _round(modeled_total),
        "delta_total_return": _round(modeled_total - fixed_total),
        "improvement": improvement,
        # The gate only opens on a REAL-snapshot improvement; the offline fixture
        # is a mechanics/regression check and is never re-baseline-eligible.
        "rebaseline_eligible": bool(basis == "real_bars" and improvement),
        "rebaseline_gate": "do_not_rebaseline_without_real_snapshot_improvement",
    }


def build_report(snapshot: str) -> dict[str, Any]:
    candidates = _load_candidates(snapshot)
    shipped = current_shipped_defaults()
    expected = {key: value for key, value in SELECTED_DEFAULT.items() if key in shipped}
    divergences = {
        key: {"selected_default": expected[key], "shipped": shipped.get(key)}
        for key in sorted(expected)
        if shipped.get(key) != expected[key]
    }
    return {
        "snapshot_id": snapshot,
        "schema_version": 1,
        "methods": {
            "level_method": "bounded_atr_risk_with_reward_ceiling",
            "fair_value_basis_candidates": ["valuation_yields", "intrinsic_model"],
            "sizing_conviction_candidates": ["fair_value", "inverse_vol", "strategy_rank", "none"],
        },
        "realism_metrics": _realism_metrics(candidates),
        "robustness_metrics": {
            "deterministic_sort": "ticker",
            "sample_count": len(candidates),
            "stability": "byte-identical regeneration required by test",
        },
        "coverage_metrics": _coverage_metrics(candidates),
        "sizing_metrics": _sizing_metrics(candidates),
        "backtest_baseline_delta": _backtest_delta(candidates),
        "selected_default": SELECTED_DEFAULT,
        "shipped_defaults": shipped,
        "shipped_defaults_match_selected": not divergences,
        "default_divergences": divergences,
    }


def dumps_report(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def write_report(report: dict[str, Any], output: Path | None = None) -> Path:
    target = output or ARTIFACT_DIR / f"{report['snapshot_id']}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dumps_report(report), encoding="utf-8")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, help="Frozen snapshot id or a JSON fixture path.")
    parser.add_argument("--out", type=Path, help="Optional output path.")
    args = parser.parse_args(argv)

    path = write_report(build_report(args.snapshot), args.out)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
