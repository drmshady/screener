"""Offline integrity harness (feature 008, T019; Decision 6, harness-report.schema.md).

Two robustness proofs that run **outside** the live screen:

  1. **Seeded-defect regression** (``run_seeded_suite``) — injects each synthetic
     defect class (data-model §9) into a copy of a frozen snapshot, runs the
     strategy's ``OutputContract`` through the shared engine, and asserts the
     expected invariant family fires. 100% detection is a blocking CI gate
     (SC-001); the un-corrupted control must stay clean (SC-002). This part is
     deterministic and network-free — it is what ``pytest tests/integrity`` gates.

  2. **Independent cross-check** (``cross_check``) — compares each top-N
     candidate's price / 52-week-high against a vendor-independent reading
     (``data/independent_quote``) and classifies the divergence
     (``classify_verdict``), distinguishing genuine staleness (``STALE``) from an
     unflagged disagreement (``DIVERGES_UNFLAGGED``, a failure). On demand,
     non-blocking — a missing source reports ``UNVERIFIED`` and never crashes
     (FR-009/FR-011).

``build_report`` serializes one run into the human-readable report of
``contracts/harness-report.schema.md``. The only non-deterministic field anywhere
is the cross-check's ``independent_fetch_at`` timestamp (FR-024/SC-005).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Iterable, List, Optional, Sequence, Set

import pandas as pd

from backend.src.data.independent_quote import IndependentQuoteProvider
from backend.src.screening.integrity.contract import OutputContract
from backend.src.screening.integrity.engine import evaluate_contract

# The operator-facing divergence threshold is fixed by the spec (research Decision 9).
DIVERGENCE_THRESHOLD = 0.10


# --------------------------------------------------------------------------- #
# Seeded defects (data-model §9)                                              #
# --------------------------------------------------------------------------- #

DefectApply = Callable[[pd.DataFrame], pd.DataFrame]


@dataclass
class SeededDefect:
    """A synthetic fault injected into a frozen-snapshot copy (data-model §9)."""

    defect_class: str
    target_ticker: str
    apply: DefectApply
    expected_family: str


@dataclass
class SeededDefectResult:
    """The outcome of injecting one defect and running the contract."""

    defect_class: str
    target_ticker: str
    expected_family: str
    detected: bool
    fired_families: tuple


def _set(df: pd.DataFrame, ticker: str, column: str, value) -> pd.DataFrame:
    df.loc[df["ticker"] == ticker, column] = value
    return df


def default_seeded_defects(target_ticker: str) -> List[SeededDefect]:
    """The seven defect classes the harness must catch (harness-report.schema §2).

    Each ``apply`` mutates a *copy* of the snapshot (the caller passes one) and is
    crafted so exactly its ``expected_family`` invariant is guaranteed to fire on
    the target row. They read/write the candidate figures and the data-model §8
    series-integrity signal columns the contract consumes.
    """

    def corrupted_price(df: pd.DataFrame) -> pd.DataFrame:
        # A grossly-wrong (stale/erroneous) close above the 52-week high: the
        # high-plausibility value-domain bound (close <= 52w_high) breaks.
        high = float(df.loc[df["ticker"] == target_ticker, "52w_high"].iloc[0])
        return _set(df, target_ticker, "close", high * 1.6)

    def broken_score(df: pd.DataFrame) -> pd.DataFrame:
        # A score that no longer reproduces return_12_1·vol_scalar/(1+dist).
        return _set(df, target_ticker, "score", 999.0)

    def stale_but_fresh(df: pd.DataFrame) -> pd.DataFrame:
        # A stale last bar presented as fresh manifests as a non-strict date
        # sequence (a repeated/duplicate date) in the backing series.
        return _set(df, target_ticker, "series_dates_ok", False)

    def nan_field(df: pd.DataFrame) -> pd.DataFrame:
        return _set(df, target_ticker, "return_12_1", float("nan"))

    def inconsistent_dist_to_high(df: pd.DataFrame) -> pd.DataFrame:
        # dist_to_high no longer equals (52w_high - close)/close.
        return _set(df, target_ticker, "dist_to_high", 0.99)

    def seam_discontinuity(df: pd.DataFrame) -> pd.DataFrame:
        # Verified inconsistent: an overlap existed but the adjustment factor was
        # unstable -> the strong `series.seam_consistent` flag.
        df = _set(df, target_ticker, "seam_overlap_found", True)
        return _set(df, target_ticker, "seam_consistent", False)

    def seam_unverified(df: pd.DataFrame) -> pd.DataFrame:
        # Couldn't verify: no overlapping bars across the seam -> the soft
        # `series.seam_unverified` flag (distinct from a verified inconsistency).
        df = _set(df, target_ticker, "seam_overlap_found", False)
        return _set(df, target_ticker, "seam_consistent", False)

    def share_class_swap(df: pd.DataFrame) -> pd.DataFrame:
        return _set(df, target_ticker, "share_class_consistent", False)

    def unexplained_jump_with_dividend(df: pd.DataFrame) -> pd.DataFrame:
        # A genuine bad-bar spike (large single-session move) co-occurring with a
        # routine corporate action SOMEWHERE in the window. A window-wide action
        # flag must NOT excuse this unrelated jump — only a localized action at
        # the jumping session does. Guards against regression of the masking bug.
        df = _set(df, target_ticker, "series_max_session_move", 0.6)
        df = _set(df, target_ticker, "corporate_action_in_window", True)
        df = _set(df, target_ticker, "series_max_move_explained", False)
        return df

    return [
        SeededDefect("corrupted_price", target_ticker, corrupted_price, "value_domain"),
        SeededDefect("broken_score", target_ticker, broken_score, "score"),
        SeededDefect("stale_but_fresh", target_ticker, stale_but_fresh, "series"),
        SeededDefect("nan_field", target_ticker, nan_field, "value_domain"),
        SeededDefect(
            "inconsistent_dist_to_high",
            target_ticker,
            inconsistent_dist_to_high,
            "coherence",
        ),
        SeededDefect("seam_discontinuity", target_ticker, seam_discontinuity, "series"),
        SeededDefect("seam_unverified", target_ticker, seam_unverified, "series"),
        SeededDefect("share_class_swap", target_ticker, share_class_swap, "identity"),
        SeededDefect(
            "unexplained_jump_with_dividend",
            target_ticker,
            unexplained_jump_with_dividend,
            "series",
        ),
    ]


def run_seeded_defect(
    snapshot_df: pd.DataFrame,
    contract: OutputContract,
    defect: SeededDefect,
) -> SeededDefectResult:
    """Inject one defect into a snapshot copy and check the contract catches it."""
    corrupted = defect.apply(snapshot_df.copy(deep=True))
    annotated = evaluate_contract(corrupted, contract)
    matches = annotated.loc[annotated["ticker"] == defect.target_ticker]
    fired: tuple = ()
    if not matches.empty:
        violations = matches.iloc[0]["data_integrity_warnings"]
        fired = tuple(v.family for v in violations)
    return SeededDefectResult(
        defect_class=defect.defect_class,
        target_ticker=defect.target_ticker,
        expected_family=defect.expected_family,
        detected=defect.expected_family in fired,
        fired_families=fired,
    )


def run_seeded_suite(
    snapshot_df: pd.DataFrame,
    contract: OutputContract,
    *,
    target_ticker: Optional[str] = None,
    defects: Optional[Sequence[SeededDefect]] = None,
) -> List[SeededDefectResult]:
    """Run every seeded defect; ``snapshot_df`` is never mutated (each works on a
    deep copy). ``target_ticker`` defaults to the first row's ticker."""
    if defects is None:
        if target_ticker is None:
            target_ticker = str(snapshot_df["ticker"].iloc[0])
        defects = default_seeded_defects(target_ticker)
    return [run_seeded_defect(snapshot_df, contract, d) for d in defects]


def control_is_clean(snapshot_df: pd.DataFrame, contract: OutputContract) -> bool:
    """True iff the un-corrupted snapshot raises no candidate-severity warning."""
    annotated = evaluate_contract(snapshot_df, contract)
    return not bool(annotated["data_suspect"].any())


# --------------------------------------------------------------------------- #
# Independent cross-check (data-model §10)                                    #
# --------------------------------------------------------------------------- #


@dataclass
class CrossCheckVerdict:
    """One top-N candidate's screener-vs-independent comparison (data-model §10)."""

    ticker: str
    screener_price: Optional[float]
    screener_52w_high: Optional[float]
    independent_price: Optional[float]
    independent_52w_high: Optional[float]
    divergence_pct: Optional[float]
    verdict: str
    independent_fetch_at: str


def compute_divergence(
    screener_price: Optional[float], independent_price: Optional[float]
) -> Optional[float]:
    """Relative divergence ``|screener - independent| / independent`` (None when
    the independent figure is missing or zero)."""
    if screener_price is None or independent_price is None:
        return None
    try:
        ind = float(independent_price)
        scr = float(screener_price)
    except (TypeError, ValueError):
        return None
    if ind == 0 or math.isnan(ind) or math.isnan(scr):
        return None
    return abs(scr - ind) / abs(ind)


def classify_verdict(
    *,
    screener_price: Optional[float],
    independent_price: Optional[float],
    has_warning: bool,
    stale: bool,
    threshold: float = DIVERGENCE_THRESHOLD,
) -> str:
    """Assign a cross-check verdict (harness-report.schema §3 / FR-010/FR-011).

    Ordering matters: an unavailable source is ``UNVERIFIED`` regardless of
    anything else; within a real divergence, genuine staleness (``STALE``) is
    distinguished from a real disagreement so an honestly-old last bar is never
    mislabelled ``DIVERGES_UNFLAGGED`` (FR-011).
    """
    divergence = compute_divergence(screener_price, independent_price)
    if divergence is None:
        return "UNVERIFIED"
    if divergence < threshold:
        return "AGREES"
    if stale:
        return "STALE"
    return "DIVERGES_AND_FLAGGED" if has_warning else "DIVERGES_UNFLAGGED"


def _opt_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def cross_check(
    snapshot_df: pd.DataFrame,
    contract: OutputContract,
    provider: IndependentQuoteProvider,
    *,
    top_n: int = 10,
    threshold: float = DIVERGENCE_THRESHOLD,
    stale_tickers: Optional[Set[str]] = None,
) -> List[CrossCheckVerdict]:
    """Cross-check the top-N candidates against the independent vendor (FR-010).

    The screener side is deterministic: the contract is evaluated once to know
    which names carry a data-integrity warning, then each candidate is compared to
    its independent quote. Staleness is taken from the snapshot's ``last_bar_stale``
    column (when present) unioned with the explicit ``stale_tickers`` override, so
    an honestly-old bar resolves to ``STALE`` not ``DIVERGES_UNFLAGGED`` (FR-011).
    Only ``independent_fetch_at`` is non-deterministic (FR-024).
    """
    top = snapshot_df.head(max(0, top_n))
    annotated = evaluate_contract(top, contract)
    overrides = set(stale_tickers or set())
    has_stale_col = "last_bar_stale" in annotated.columns

    verdicts: List[CrossCheckVerdict] = []
    for _, row in annotated.iterrows():
        ticker = str(row["ticker"])
        screener_price = _opt_float(row.get("close"))
        screener_high = _opt_float(row.get("52w_high"))
        quote = provider.quote(ticker)
        fetch_at = datetime.now(timezone.utc).isoformat()

        independent_price = quote.price if quote.available else None
        independent_high = quote.high_52w if quote.available else None
        divergence = compute_divergence(screener_price, independent_price)

        stale = ticker in overrides or (
            has_stale_col and bool(row.get("last_bar_stale"))
        )
        verdict = classify_verdict(
            screener_price=screener_price,
            independent_price=independent_price,
            has_warning=bool(row.get("data_suspect", False)),
            stale=stale,
            threshold=threshold,
        )
        verdicts.append(
            CrossCheckVerdict(
                ticker=ticker,
                screener_price=screener_price,
                screener_52w_high=screener_high,
                independent_price=independent_price,
                independent_52w_high=independent_high,
                divergence_pct=divergence,
                verdict=verdict,
                independent_fetch_at=fetch_at,
            )
        )
    return verdicts


# --------------------------------------------------------------------------- #
# Report assembly (contracts/harness-report.schema.md)                        #
# --------------------------------------------------------------------------- #


@dataclass
class HarnessReport:
    """The structured result of one harness run (serialized by ``render``)."""

    snapshot_as_of: str
    snapshot_id: str
    independent_source: str
    independent_fetch_at: Optional[str]
    seeded_results: List[SeededDefectResult]
    control_clean: bool
    cross_check_verdicts: List[CrossCheckVerdict]
    run_date: str = field(
        default_factory=lambda: datetime.now(timezone.utc).date().isoformat()
    )

    @property
    def seeded_detected(self) -> int:
        return sum(1 for r in self.seeded_results if r.detected)

    @property
    def seeded_missed(self) -> int:
        return sum(1 for r in self.seeded_results if not r.detected)

    @property
    def diverges_unflagged(self) -> int:
        return sum(1 for v in self.cross_check_verdicts if v.verdict == "DIVERGES_UNFLAGGED")

    @property
    def overall_pass(self) -> bool:
        # Blocking criteria ONLY: 100% seeded detection (SC-001) and no unflagged
        # divergence (SC-004). SC-002 (no false positives) is a property of
        # KNOWN-CLEAN data and is gated separately by the seeded suite's
        # clean-fixture control test — a LIVE snapshot legitimately carries real
        # flags, which are findings to review (adjudicated by the cross-check),
        # NOT a control failure. Conflating the two failed every healthy live run.
        return self.seeded_missed == 0 and self.diverges_unflagged == 0


def _fmt(value: Optional[float], pct: bool = False) -> str:
    if value is None:
        return "—"
    return f"{value:.1%}" if pct else f"{value:.2f}"


def render_report(report: HarnessReport) -> str:
    """Render ``report`` to the markdown of harness-report.schema.md (§1–§5)."""
    verdict_counts: dict[str, int] = {}
    for v in report.cross_check_verdicts:
        verdict_counts[v.verdict] = verdict_counts.get(v.verdict, 0) + 1
    counts_str = ", ".join(f"{k}={v}" for k, v in sorted(verdict_counts.items())) or "—"

    lines: List[str] = []
    lines.append("# Offline Integrity Harness Report")
    lines.append("")
    lines.append(f"**Feature**: 008-momentum-data-integrity")
    lines.append("")

    # §1 Run Header
    lines.append("## 1. Run Header")
    lines.append("")
    lines.append(f"- run_date: {report.run_date}")
    lines.append(f"- snapshot_as_of: {report.snapshot_as_of}")
    lines.append(f"- snapshot_id: {report.snapshot_id}")
    lines.append(f"- independent_source: {report.independent_source}")
    lines.append(f"- independent_fetch_at: {report.independent_fetch_at or '—'}")
    lines.append(
        f"- **Overall verdict**: {'pass' if report.overall_pass else 'fail'}"
    )
    lines.append(
        f"- Seeded defects: injected {len(report.seeded_results)} / "
        f"detected {report.seeded_detected} / missed {report.seeded_missed}"
    )
    lines.append(f"- Cross-check verdicts: {counts_str}")
    lines.append("")

    # §2 Seeded-Defect Results
    lines.append("## 2. Seeded-Defect Results (FR-008, SC-001)")
    lines.append("")
    lines.append("| Defect class | Target | Expected family | Detected | Result |")
    lines.append("|--------------|--------|-----------------|----------|--------|")
    for r in report.seeded_results:
        mark = "✓" if r.detected else "✗"
        result = "PASS" if r.detected else "**FAIL**"
        lines.append(
            f"| {r.defect_class} | {r.target_ticker} | {r.expected_family} | "
            f"{mark} | {result} |"
        )
    lines.append("")
    if report.control_clean:
        lines.append(
            "Un-corrupted snapshot raises no data-integrity warning (clean baseline)."
        )
    else:
        lines.append(
            "Un-corrupted snapshot carries pre-existing data-integrity flag(s). On a "
            "LIVE snapshot these are genuine findings (see §2/§3; the cross-check "
            "adjudicates whether each is a true defect), NOT a false positive. SC-002 "
            "(no false positives on clean data) is gated separately by the seeded "
            "suite's clean-fixture control test, not by this live run."
        )
    lines.append("")

    # §3 Independent Cross-Check
    lines.append("## 3. Independent Cross-Check (FR-010/FR-011, SC-003/SC-004)")
    lines.append("")
    lines.append(
        "| Ticker | Screener price | Independent price | Divergence % | "
        "Screener 52w-high | Independent 52w-high | Verdict |"
    )
    lines.append(
        "|--------|----------------|-------------------|--------------|"
        "-------------------|----------------------|---------|"
    )
    for v in report.cross_check_verdicts:
        lines.append(
            f"| {v.ticker} | {_fmt(v.screener_price)} | {_fmt(v.independent_price)} | "
            f"{_fmt(v.divergence_pct, pct=True)} | {_fmt(v.screener_52w_high)} | "
            f"{_fmt(v.independent_52w_high)} | {v.verdict} |"
        )
    lines.append("")
    lines.append(
        f"DIVERGES_UNFLAGGED count: {report.diverges_unflagged} "
        f"(zero required for pass — SC-004)."
    )
    lines.append("")

    # §4 Determinism Statement
    lines.append("## 4. Determinism Statement (FR-024/SC-005)")
    lines.append("")
    lines.append(
        "The screener side of every verdict is a pure function of the frozen "
        "snapshot and is byte-identical across two runs of the same snapshot; only "
        "`independent_fetch_at` varies between runs."
    )
    lines.append("")

    # §5 Verdict & Actions
    lines.append("## 5. Verdict & Actions")
    lines.append("")
    if report.overall_pass:
        lines.append(
            "Go: 100% seeded detection and zero DIVERGES_UNFLAGGED in the cross-check."
        )
        if not report.control_clean:
            lines.append(
                "Note: the live snapshot carries pre-existing data-integrity flag(s) "
                "to review (§2/§3) — these are findings, not a gate failure."
            )
    else:
        lines.append("No-go. Must-fix:")
        for r in report.seeded_results:
            if not r.detected:
                lines.append(
                    f"- seeded `{r.defect_class}` not caught — expected family "
                    f"`{r.expected_family}` did not fire (invariants for that family)."
                )
        for v in report.cross_check_verdicts:
            if v.verdict == "DIVERGES_UNFLAGGED":
                lines.append(
                    f"- {v.ticker}: independent price diverges "
                    f"{_fmt(v.divergence_pct, pct=True)} but the screener did NOT "
                    "flag it (DIVERGES_UNFLAGGED — investigate the figure)."
                )
    lines.append("")
    return "\n".join(lines)


def run_harness(
    snapshot_df: pd.DataFrame,
    contract: OutputContract,
    provider: Optional[IndependentQuoteProvider] = None,
    *,
    snapshot_as_of: str,
    snapshot_id: str = "frozen",
    top_n: int = 10,
    stale_tickers: Optional[Set[str]] = None,
) -> HarnessReport:
    """Run both halves of the harness and return a structured ``HarnessReport``.

    The seeded suite always runs (deterministic, no network). The cross-check runs
    only when a ``provider`` is supplied; otherwise its section is empty and the
    overall verdict rests on the seeded gate (Decision 6 — a network outage never
    fails the build).
    """
    target = str(snapshot_df["ticker"].iloc[0]) if not snapshot_df.empty else ""
    seeded = run_seeded_suite(snapshot_df, contract, target_ticker=target)
    control_clean = control_is_clean(snapshot_df, contract)

    verdicts: List[CrossCheckVerdict] = []
    source = "none"
    fetch_at: Optional[str] = None
    if provider is not None:
        verdicts = cross_check(
            snapshot_df,
            contract,
            provider,
            top_n=top_n,
            stale_tickers=stale_tickers,
        )
        if verdicts:
            fetch_at = verdicts[0].independent_fetch_at
            source = next(
                (
                    "finnhub/alpha_vantage"
                    for v in verdicts
                    if v.independent_price is not None
                ),
                "unavailable",
            )

    return HarnessReport(
        snapshot_as_of=snapshot_as_of,
        snapshot_id=snapshot_id,
        independent_source=source,
        independent_fetch_at=fetch_at,
        seeded_results=seeded,
        control_clean=control_clean,
        cross_check_verdicts=verdicts,
    )
