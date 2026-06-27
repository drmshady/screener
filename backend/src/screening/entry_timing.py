from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd

from backend.src.models.strategy import (
    Disqualifier,
    EntryComponent,
    EntryDiagnostics,
    EntryTimingClassification,
)


@dataclass(frozen=True)
class EntryThresholds:
    pivot_max_extension: float = 0.05
    volume_ratio_min: float = 1.4
    volume_ratio_preferred: float = 1.5
    flat_min_weeks: float = 5.0
    cup_min_weeks: float = 7.0
    base_depth_max: float = 0.33
    sma200_extension_max: float = 0.40
    climax_advance_min: float = 0.25
    climax_prior_trend_weeks: float = 8.0
    huge_gap_threshold: float = 0.05


def _float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _component(name: str, status: str, value: float | None, reason: str) -> EntryComponent:
    return EntryComponent(name=name, status=status, value=value, reason=reason)


def _status_from_bound(value: float | None, bound: float, pass_reason: str, fail_reason: str) -> tuple[str, str]:
    if value is None:
        return "undetermined", "insufficient data to assess entry"
    if value <= bound:
        return "pass", pass_reason
    return "fail", fail_reason


def classify_entry_timing(
    row: Mapping[str, Any], *, thresholds: EntryThresholds
) -> EntryTimingClassification:
    close = _float(row.get("close"))
    sma_200 = _float(row.get("sma_200"))
    pivot = _float(row.get("pivot"))
    base_type = str(row.get("base_type") or "none")
    base_length_weeks = _float(row.get("base_length_weeks"))
    base_depth = _float(row.get("base_depth"))
    breakout_volume_ratio = _float(row.get("breakout_volume_ratio"))
    dist_above_pivot = _float(row.get("dist_above_pivot"))
    dist_above_sma_200 = _float(row.get("dist_above_sma_200"))

    components: list[EntryComponent] = []

    if pivot is None or base_type == "none":
        dist_above_pivot = None

    status, reason = _status_from_bound(
        dist_above_pivot,
        thresholds.pivot_max_extension,
        "near pivot",
        f"extended >{thresholds.pivot_max_extension:.0%} above pivot",
    )
    if dist_above_pivot is not None and dist_above_pivot < 0:
        status, reason = "undetermined", "below detected pivot"
    components.append(_component("pivot_proximity", status, dist_above_pivot, reason))

    if close is None or sma_200 is None or sma_200 <= 0:
        components.append(_component("trend", "undetermined", None, "200-day SMA unavailable"))
    elif close > sma_200:
        components.append(_component("trend", "pass", 1.0, "above 200-day SMA"))
    else:
        components.append(_component("trend", "fail", 0.0, "at or below 200-day SMA"))

    if breakout_volume_ratio is None:
        components.append(
            _component("volume_confirmation", "undetermined", None, "50-day volume baseline unavailable")
        )
    elif breakout_volume_ratio >= thresholds.volume_ratio_min:
        reason = (
            "strong confirming volume"
            if breakout_volume_ratio >= thresholds.volume_ratio_preferred
            else "confirming volume"
        )
        components.append(_component("volume_confirmation", "pass", breakout_volume_ratio, reason))
    else:
        components.append(
            _component("volume_confirmation", "fail", breakout_volume_ratio, "weak-volume breakout")
        )

    min_weeks = thresholds.flat_min_weeks if base_type == "flat" else thresholds.cup_min_weeks
    if base_type == "none" or base_length_weeks is None:
        components.append(_component("base_maturity", "undetermined", None, "base not detected"))
    elif base_length_weeks >= min_weeks:
        components.append(_component("base_maturity", "pass", base_length_weeks, "mature base"))
    else:
        components.append(_component("base_maturity", "fail", base_length_weeks, "immature base"))

    status, reason = _status_from_bound(
        base_depth,
        thresholds.base_depth_max,
        "base depth in range",
        "base too deep",
    )
    if base_type == "none":
        status, reason = "undetermined", "base not detected"
    components.append(_component("base_depth", status, base_depth, reason))

    status, reason = _status_from_bound(
        dist_above_sma_200,
        thresholds.sma200_extension_max,
        "not extended from SMA-200",
        "far above SMA-200",
    )
    components.append(_component("not_extended", status, dist_above_sma_200, reason))

    climax_advance = _float(row.get("climax_advance"))
    prior_trend_weeks = _float(row.get("prior_trend_weeks")) or 0.0
    climax_triggered = bool(
        climax_advance is not None
        and climax_advance >= thresholds.climax_advance_min
        and prior_trend_weeks >= thresholds.climax_prior_trend_weeks
    )
    gap_above_pivot = _float(row.get("gap_above_pivot"))
    huge_gap_triggered = bool(
        gap_above_pivot is not None and gap_above_pivot > thresholds.huge_gap_threshold
    )
    catalyst_triggered = bool(row.get("recent_short_lived_catalyst", False))
    disqualifiers = [
        Disqualifier(
            name="climax_top",
            triggered=climax_triggered,
            value=climax_advance,
            reason="climax-top exhaustion" if climax_triggered else "no climax-top exhaustion signal",
            forces_not_entry_ready=True,
        ),
        Disqualifier(
            name="huge_gap",
            triggered=huge_gap_triggered,
            value=gap_above_pivot,
            reason="gap-extended above pivot" if huge_gap_triggered else "no gap-extension signal",
            forces_not_entry_ready=True,
        ),
        Disqualifier(
            name="short_lived_catalyst",
            triggered=catalyst_triggered,
            value=None,
            reason=(
                "elevated post-catalyst pullback risk"
                if catalyst_triggered
                else "no recent short-lived catalyst signal"
            ),
            forces_not_entry_ready=False,
        ),
    ]

    has_failure = any(component.status == "fail" for component in components)
    has_undetermined = any(component.status == "undetermined" for component in components)
    has_forcing = any(d.triggered and d.forces_not_entry_ready for d in disqualifiers)
    if has_failure or has_forcing:
        state = "not_entry_ready"
    elif has_undetermined:
        state = "entry_undetermined"
    else:
        state = "entry_ready"

    failed_or_unknown = [
        component.reason
        for component in components
        if component.status in {"fail", "undetermined"}
    ]
    if state == "entry_ready":
        summary = "near pivot, uptrend, confirming volume"
    else:
        summary = "; ".join(failed_or_unknown[:3]) or "entry timing mixed"

    return EntryTimingClassification(
        state=state,
        components=components,
        disqualifiers=disqualifiers,
        diagnostics=EntryDiagnostics(
            pivot=pivot,
            base_type=base_type if base_type in {"flat", "cup", "cup_with_handle", "double_bottom", "none"} else "none",
            base_length_weeks=base_length_weeks,
            base_depth=base_depth,
            breakout_volume_ratio=breakout_volume_ratio,
            dist_above_pivot=dist_above_pivot,
            dist_above_sma_200=dist_above_sma_200,
        ),
        summary=summary,
    )
