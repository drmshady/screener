"""Fixed-reference-universe thresholds for the cross-sectional gates.

Gross profitability (Novy-Marx) and asset growth (Cooper-Gulen-Schill) are
cross-sectional anomalies: a name's pass/fail is its rank vs peers. Computing the
"top/bottom half" cut against *that screen's* filtered universe makes the cut move
with filter choices (Shariah on/off) and universe size, so the SAME name can flip
between the screen and single-ticker analysis (e.g. EA: top-half GP vs the ~651
compliant set, bottom-half vs the full ~3576 universe).

To keep the gate stable, we compute the GP/AG percentile *thresholds* once over a
broad canonical reference universe and cache the two numbers here. The screen and
analyze then apply those absolute thresholds, so a name's verdict no longer
depends on which filtered slice it happens to be screened in. Refreshed alongside
prices (see refresh_reference_thresholds in the engine).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_PATH = Path(__file__).resolve().parents[3] / "data" / "reference_thresholds.json"


def load_reference_thresholds() -> dict | None:
    """Cached {gp_threshold, ag_threshold, value_composite_threshold, as_of,
    universe_size} or None. The value-composite cut is optional (older caches
    predate it); callers must tolerate its absence."""
    try:
        with open(_PATH, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if (
        payload.get("gp_threshold") is None
        and payload.get("ag_threshold") is None
        and payload.get("value_composite_threshold") is None
    ):
        return None
    return payload


def compute_value_composite_threshold(
    df: pd.DataFrame, top_percentile: float
) -> float | None:
    """Reference cut for the value composite: keep names at/above this score
    (cheapest top fraction). `top_percentile` is the fraction kept (0.5 = cheapest
    half), so the threshold is the (1 - top_percentile) quantile of the composite.
    Returns None when the composite is absent/empty or the cut is disabled."""
    if not (0.0 < top_percentile < 1.0) or "value_composite" not in df.columns:
        return None
    valid = pd.to_numeric(df["value_composite"], errors="coerce").dropna()
    if valid.empty:
        return None
    return float(valid.quantile(1.0 - top_percentile))


def compute_thresholds(
    df: pd.DataFrame, gp_percentile: float, ag_percentile: float
) -> tuple[float | None, float | None]:
    """GP (>= keep) and AG (<= keep) cut values over the reference universe df."""
    gp_threshold: float | None = None
    ag_threshold: float | None = None
    if "gp_to_assets" in df.columns:
        gp_valid = pd.to_numeric(df["gp_to_assets"], errors="coerce").dropna()
        if not gp_valid.empty:
            gp_threshold = float(gp_valid.quantile(gp_percentile))
    if ag_percentile < 1.0 and "asset_growth" in df.columns:
        ag_valid = pd.to_numeric(df["asset_growth"], errors="coerce").dropna()
        if not ag_valid.empty:
            ag_threshold = float(ag_valid.quantile(ag_percentile))
    return gp_threshold, ag_threshold


def save_reference_thresholds(
    gp_threshold: float | None,
    ag_threshold: float | None,
    *,
    universe_size: int,
    as_of: str | None,
    value_composite_threshold: float | None = None,
) -> dict:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "gp_threshold": gp_threshold,
        "ag_threshold": ag_threshold,
        "value_composite_threshold": value_composite_threshold,
        "universe_size": int(universe_size),
        "as_of": as_of,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return payload
