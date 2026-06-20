"""Reusable invariant builders (feature 008, T011; momentum-contract.md).

Factory functions that return :class:`Invariant`s for the strategy-agnostic
engine (``integrity/engine.py``). They are grouped by family — ``coherence``,
``gate``, ``score``, ``level``, ``value_domain``, ``series``, ``identity`` — and
composed into a strategy's ``OUTPUT_CONTRACT`` (momentum: T012, value: T014).

Each predicate is a pure ``(row, signals) -> bool`` (``True`` == satisfied). It
reads only the candidate row plus the precomputed series-integrity ``signals``
columns (data-model §8) and never re-fetches (Decision 7). Two deliberate
conventions keep false positives at zero (FR-005 / SC-002):

  * A figure that is *missing* or non-numeric is **not** this invariant's concern
    (return satisfied) — finiteness/presence is owned by ``value_domain_finite``.
  * A series-integrity signal that is *absent* (pre-US3, before the snapshot loop
    populates §8 columns) **defaults safe** — so US1 is independently testable via
    direct figure corruption before the US3 remediation lands.
"""
from __future__ import annotations

import math
from typing import Any, Callable, Iterable, List, Optional

import pandas as pd

from backend.src.screening.integrity.contract import Invariant

# Pure formula over (row, signals) -> expected numeric value.
ComputeFn = Callable[[Any, Any], Any]


def _get(container: Any, key: str, default: Any = None) -> Any:
    """Read ``key`` from a pandas Series / mapping; ``default`` when absent."""
    if container is None:
        return default
    getter = getattr(container, "get", None)
    if callable(getter):
        try:
            return getter(key, default)
        except TypeError:
            pass
    try:
        return container[key]
    except (KeyError, IndexError, TypeError):
        return default


def _to_float(value: Any) -> Optional[float]:
    """Coerce to float; ``None`` for missing/non-numeric. NaN/inf pass through."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _finite(value: Any) -> Optional[float]:
    """As :func:`_to_float`, but ``None`` for NaN/inf too — i.e. a usable number."""
    f = _to_float(value)
    if f is None or not math.isfinite(f):
        return None
    return f


_VERIFY = "verify before acting"


# --- coherence ------------------------------------------------------------

def coherence_dist_to_high(*, tol: float = 1e-6) -> Invariant:
    """``dist_to_high == (52w_high − close)/close`` (within tolerance)."""

    def predicate(row, signals) -> bool:
        close = _finite(_get(row, "close"))
        high = _finite(_get(row, "52w_high"))
        dist = _finite(_get(row, "dist_to_high"))
        if close is None or high is None or dist is None or close == 0:
            return True
        return abs(dist - (high - close) / close) <= tol

    return Invariant(
        name="coherence.dist_to_high",
        family="coherence",
        severity="candidate",
        predicate=predicate,
        figure="dist_to_high",
        message=(
            "distance-to-high does not match (52-week high − close) / close — a "
            f"displayed figure is inconsistent; {_VERIFY}"
        ),
    )


def coherence_entry_eq_close(*, tol: float = 0.01) -> Invariant:
    """The displayed entry equals the latest close (data-model Decision 1)."""

    def predicate(row, signals) -> bool:
        entry = _finite(_get(row, "entry"))
        close = _finite(_get(row, "close"))
        if entry is None or close is None:
            return True
        return abs(entry - close) <= tol

    return Invariant(
        name="coherence.entry_eq_close",
        family="coherence",
        severity="candidate",
        predicate=predicate,
        figure="entry",
        message=f"entry price does not equal the latest close; {_VERIFY}",
    )


# --- gate satisfaction ----------------------------------------------------

def gate_satisfied(
    *,
    name: str,
    figure: Optional[str],
    column: str,
    threshold: float,
    message: str,
    comparator: str = "<=",
    tol: float = 1e-9,
) -> Invariant:
    """A listed candidate must actually satisfy the strategy's hard gate at the
    stated parameter (catches the "listed-but-doesn't-pass" defect, US1-AC3)."""

    def predicate(row, signals) -> bool:
        val = _finite(_get(row, column))
        if val is None:
            return True
        if comparator == "<=":
            return val <= threshold + tol
        if comparator == ">=":
            return val >= threshold - tol
        raise ValueError(f"unsupported comparator {comparator!r}")

    return Invariant(
        name=name,
        family="gate",
        severity="candidate",
        predicate=predicate,
        figure=figure,
        message=message,
    )


# --- score reproduction ---------------------------------------------------

def score_reproduces(
    *,
    compute: ComputeFn,
    name: str = "score.reproduces",
    figure: str = "score",
    rel_tol: float = 1e-3,
    abs_tol: float = 1e-9,
    message: Optional[str] = None,
) -> Invariant:
    """The reported score reproduces its declared formula within tolerance."""

    msg = message or (
        "score does not reproduce its declared ranking formula — the ranking "
        f"figure may be wrong; {_VERIFY}"
    )

    def predicate(row, signals) -> bool:
        actual = _finite(_get(row, figure))
        if actual is None:
            return True
        try:
            expected = _finite(compute(row, signals))
        except Exception:
            return True
        if expected is None:
            return True
        return abs(actual - expected) <= max(abs_tol, rel_tol * abs(expected))

    return Invariant(
        name=name,
        family="score",
        severity="candidate",
        predicate=predicate,
        figure=figure,
        message=msg,
    )


# --- level sanity ---------------------------------------------------------

def level_sanity(
    *,
    r_multiple: float,
    tol: float = 1e-2,
    message_ordering: Optional[str] = None,
    message_r: Optional[str] = None,
) -> List[Invariant]:
    """``level.ordering`` (``0 < stop < entry < take_profit``) and
    ``level.r_multiple`` (take-profit is the declared reward:risk multiple)."""

    def ordering_pred(row, signals) -> bool:
        stop = _finite(_get(row, "stop_loss"))
        entry = _finite(_get(row, "entry"))
        tp = _finite(_get(row, "take_profit"))
        if stop is None or entry is None or tp is None:
            return True
        return 0 < stop < entry < tp

    def r_pred(row, signals) -> bool:
        stop = _finite(_get(row, "stop_loss"))
        entry = _finite(_get(row, "entry"))
        tp = _finite(_get(row, "take_profit"))
        if stop is None or entry is None or tp is None:
            return True
        risk = entry - stop
        if risk <= 0:
            return True  # the ordering invariant owns this failure
        risk_distance = _finite(_get(row, "risk_distance"))
        reward_distance = _finite(_get(row, "reward_distance"))
        reward_ceiling_basis = _get(row, "reward_ceiling_basis")
        if reward_ceiling_basis is not None or reward_distance is not None:
            if risk_distance is not None and abs(risk_distance - risk) > tol:
                return False
            if reward_distance is None:
                return False
            return abs((tp - entry) - reward_distance) <= tol
        return abs((tp - entry) / risk - r_multiple) <= tol

    ordering = Invariant(
        name="level.ordering",
        family="level",
        severity="candidate",
        predicate=ordering_pred,
        figure="stop_loss",
        message=message_ordering
        or (
            "stop / entry / take-profit are not in a sane "
            f"0 < stop < entry < take-profit order; {_VERIFY}"
        ),
    )
    r_mult = Invariant(
        name="level.r_multiple",
        family="level",
        severity="candidate",
        predicate=r_pred,
        figure="take_profit",
        message=message_r
        or (
            "take-profit does not match the declared reward:risk multiple or "
            f"bounded reward-distance metadata; {_VERIFY}"
        ),
    )
    return [ordering, r_mult]


# --- value domain ---------------------------------------------------------

def value_domain_finite(
    figures: Iterable[str],
    *,
    name: str = "value_domain.finite",
    figure: Optional[str] = None,
    message: Optional[str] = None,
) -> Invariant:
    """No NaN/inf in the listed figures (catches the ``nan_field`` defect)."""

    figs = list(figures)

    def predicate(row, signals) -> bool:
        for f in figs:
            raw = _get(row, f)
            if raw is None:
                continue
            fv = _to_float(raw)
            if fv is None:
                continue  # non-numeric is not a finiteness breach
            if not math.isfinite(fv):
                return False
        return True

    return Invariant(
        name=name,
        family="value_domain",
        severity="candidate",
        predicate=predicate,
        figure=figure,
        message=message or f"a surfaced figure is not a finite number; {_VERIFY}",
    )


def value_domain_positive(
    figures: Iterable[str],
    *,
    name: str = "value_domain.positive",
    figure: Optional[str] = None,
    message: Optional[str] = None,
) -> Invariant:
    """Every listed figure is strictly positive (price/volatility sanity)."""

    figs = list(figures)

    def predicate(row, signals) -> bool:
        for f in figs:
            v = _finite(_get(row, f))
            if v is None:
                continue
            if v <= 0:
                return False
        return True

    return Invariant(
        name=name,
        family="value_domain",
        severity="candidate",
        predicate=predicate,
        figure=figure or (figs[0] if figs else None),
        message=message
        or f"a price or volatility figure is not positive; {_VERIFY}",
    )


def value_domain_bounded(
    *,
    name: str,
    figure: str,
    limit: float,
    message: str,
) -> Invariant:
    """Generic symmetric magnitude guard (``|figure| <= limit``). This is the
    reusable form the value strategy's implausibility backstop is expressed in
    (FR-006): every yield shares the market-cap denominator, so a corrupted cap
    makes one blow past its bound."""

    def predicate(row, signals) -> bool:
        v = _finite(_get(row, figure))
        if v is None:
            return True
        return abs(v) <= limit

    return Invariant(
        name=name,
        family="value_domain",
        severity="candidate",
        predicate=predicate,
        figure=figure,
        message=message,
    )


def value_domain_return_plausible(
    *,
    lower: float = -0.95,
    upper: float = 9.0,
    figure: str = "return_12_1",
    name: str = "value_domain.return_plausible",
    message: Optional[str] = None,
) -> Invariant:
    """``lower <= return_12_1 <= upper`` — the momentum analogue of the value
    backstop. A mis-adjusted series (the BELFB seam defect) produces a return
    outside this band (momentum-contract.md)."""

    def predicate(row, signals) -> bool:
        v = _finite(_get(row, figure))
        if v is None:
            return True
        return lower <= v <= upper

    return Invariant(
        name=name,
        family="value_domain",
        severity="candidate",
        predicate=predicate,
        figure=figure,
        message=message
        or (
            "12-1 momentum is outside the plausible range "
            f"[{lower:.0%}, {upper:.0%}] — the price series may be mis-adjusted "
            f"across a data seam; {_VERIFY}"
        ),
    )


def value_domain_high_plausible(
    *,
    h_max: float = 12.0,
    name: str = "value_domain.high_plausible",
    message: Optional[str] = None,
) -> Invariant:
    """``close <= 52w_high <= close * h_max`` — a 52-week high below the current
    close is impossible; one absurdly above it signals a bad bar."""

    def predicate(row, signals) -> bool:
        close = _finite(_get(row, "close"))
        high = _finite(_get(row, "52w_high"))
        if close is None or high is None or close <= 0:
            return True
        return close <= high <= close * h_max

    return Invariant(
        name=name,
        family="value_domain",
        severity="candidate",
        predicate=predicate,
        figure="52w_high",
        message=message
        or (
            "the 52-week high is not consistent with the current close (below it, "
            f"or implausibly far above it); {_VERIFY}"
        ),
    )


def value_domain_realized_vol_floor(
    *,
    min_annualized_vol: float = 0.08,
    vol_scalar_cap: float = 2.0,
    returns_column: str = "daily_returns",
    trading_days: float = 252.0,
    name: str = "value_domain.realized_vol_floor",
    figure: str = "vol_scalar",
    message: Optional[str] = None,
) -> Invariant:
    """Flag a candidate whose trailing realized volatility has collapsed below a
    floor no freely-trading equity sustains — the signature of a price *pinned*
    under a pending all-cash acquisition / cash tender (e.g. EA pinned at its $210
    offer, realized vol ~6%). A collapsed realized vol SATURATES the
    Barroso-Santa-Clara ``vol_scalar`` at its cap, which then inflates the momentum
    score, so a merger-arb pin ranks as if it were clean low-vol momentum.

    Deterministic and no-network (Decision 7): realized vol is read from the row's
    precomputed ``daily_returns`` window — the exact series the scaler used, so the
    annualized std reproduces ``calculate_volatility_scalar``'s denominator. When
    that window is absent (fixtures / direct-figure tests), a ``vol_scalar``
    saturated at its cap is itself the pin signal (cap ⟺ realized_vol at/under the
    floor). A missing window with an unsaturated scalar is not this invariant's
    concern (fail-open, SC-002)."""

    def _annualized_vol(row) -> Optional[float]:
        raw = _get(row, returns_column)
        if raw is None:
            return None
        try:
            series = pd.Series(raw, dtype="float64").dropna()
        except (TypeError, ValueError):
            return None
        if len(series) < 2:
            return None
        sd = series.std()
        if sd is None or not math.isfinite(float(sd)):
            return None
        return float(sd) * math.sqrt(trading_days)

    def predicate(row, signals) -> bool:
        rv = _annualized_vol(row)
        if rv is not None:
            return rv >= min_annualized_vol
        # No usable returns window: a vol_scalar saturated at its cap implies a
        # realized vol already at/under the floor (cap == target/floor), so treat
        # saturation as the pin signal; an unsaturated scalar is satisfied.
        vs = _finite(_get(row, "vol_scalar"))
        if vs is None:
            return True
        return vs < vol_scalar_cap - 1e-6

    return Invariant(
        name=name,
        family="value_domain",
        severity="candidate",
        predicate=predicate,
        figure=figure,
        message=message
        or (
            "trailing realized volatility has collapsed below "
            f"{min_annualized_vol:.0%} annualized — the signature of a price pinned "
            "under a pending all-cash acquisition or cash tender, which saturates "
            f"the volatility scalar and inflates the momentum score; {_VERIFY}"
        ),
    )


# --- series integrity -----------------------------------------------------

def series_integrity(*, jump_max: float = 0.40) -> List[Invariant]:
    """``series.dates_ok``, ``series.no_unexplained_jump`` and
    ``series.seam_consistent`` — each reads only the precomputed §8 signals and
    defaults safe when those signals are absent (US1 before US3)."""

    def dates_pred(row, signals) -> bool:
        v = _get(signals, "series_dates_ok")
        if v is None:
            return True
        return bool(v)

    def jump_pred(row, signals) -> bool:
        move = _finite(_get(signals, "series_max_session_move"))
        if move is None or move <= jump_max:
            return True
        # A corporate action AT the jumping session explains the move (FR-015).
        # Prefer the LOCALIZED signal: a window-wide "action somewhere this year"
        # must not excuse an unrelated bad-bar spike (that masking let real
        # defects through). Fall back to the window-wide flag only when the
        # localized signal is absent (legacy snapshots / direct-figure US1 tests).
        explained = _get(signals, "series_max_move_explained")
        if explained is not None:
            return bool(explained)
        return bool(_get(signals, "corporate_action_in_window"))

    def seam_pred(row, signals) -> bool:
        # Strong case: the seam was VERIFIED inconsistent (an overlap existed but
        # the split/dividend factor was unstable). When there is no overlap to
        # verify, this is satisfied and `series.seam_unverified` owns the soft
        # flag. Legacy rows without the overlap signal default to the strong case
        # (preserves pre-tri-state behaviour + seeded `seam_discontinuity`).
        v = _get(signals, "seam_consistent")
        if v is None or bool(v):
            return True
        overlap = _get(signals, "seam_overlap_found")
        if overlap is None:
            return False
        return not bool(overlap)

    def seam_unverified_pred(row, signals) -> bool:
        # Soft case: the seam could NOT be verified because the two sources share
        # no overlapping bars (no factor could be computed). Not "erroneous", just
        # "couldn't confirm one basis" — a distinct, less-alarming flag.
        v = _get(signals, "seam_consistent")
        if v is None or bool(v):
            return True
        overlap = _get(signals, "seam_overlap_found")
        if overlap is None:
            return True
        return bool(overlap)

    dates = Invariant(
        name="series.dates_ok",
        family="series",
        severity="candidate",
        predicate=dates_pred,
        figure=None,
        message=(
            "the backing price history has duplicate or out-of-order dates; "
            f"{_VERIFY}"
        ),
    )
    jump = Invariant(
        name="series.no_unexplained_jump",
        family="series",
        severity="candidate",
        predicate=jump_pred,
        figure="return_12_1",
        message=(
            "the price history has a single-session jump too large to be a normal "
            f"move and not explained by a known corporate action; {_VERIFY}"
        ),
    )
    seam = Invariant(
        name="series.seam_consistent",
        family="series",
        severity="candidate",
        predicate=seam_pred,
        figure="close",
        message=(
            "the 1-year history stitches two data sources with inconsistent "
            f"split/dividend adjustment; price may be erroneous; {_VERIFY}"
        ),
    )
    seam_unverified = Invariant(
        name="series.seam_unverified",
        family="series",
        severity="candidate",
        predicate=seam_unverified_pred,
        figure="close",
        message=(
            "could not confirm a single split/dividend adjustment basis across the "
            "data-source seam — no overlapping bars to verify; treat the 1-year "
            f"price/return with caution; {_VERIFY}"
        ),
    )
    return [dates, jump, seam, seam_unverified]


# --- identity -------------------------------------------------------------

def identity_single_share_class(
    *,
    name: str = "identity.single_share_class",
    message: Optional[str] = None,
) -> Invariant:
    """Price series and fundamentals resolve to one share class (FR-014).
    Reads the ``share_class_consistent`` signal; default-safe when absent."""

    def predicate(row, signals) -> bool:
        v = _get(signals, "share_class_consistent")
        if v is None:
            return True
        return bool(v)

    return Invariant(
        name=name,
        family="identity",
        severity="candidate",
        predicate=predicate,
        figure="close",
        message=message
        or (
            "price and fundamentals may come from different share classes of the "
            f"same issuer; {_VERIFY}"
        ),
    )


# --- aggregate ------------------------------------------------------------

def aggregate_flag_count(
    *,
    name: str = "aggregate.flag_count",
    message: Optional[str] = None,
) -> Invariant:
    """Declarative marker for the aggregate family (data-model §7). It never
    fires per-row; the live caller (T013) computes the real "flagged N of M"
    data note. Present so the contract DECLARES the aggregate severity."""

    return Invariant(
        name=name,
        family="aggregate",
        severity="aggregate",
        predicate=lambda row, signals: True,
        figure=None,
        message="informational: the count of flagged names is recorded as a data note",
    )
