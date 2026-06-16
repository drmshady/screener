"""On-demand offline integrity harness runner (feature 008, T020; Decision 6).

Runs the two robustness proofs over a frozen snapshot and writes the
human-readable report of ``contracts/harness-report.schema.md``:

  * **Seeded-defect regression** — deterministic, network-free. (The same logic is
    the blocking CI gate via ``pytest tests/integrity/test_seeded_defects.py``;
    this script just includes it in the written report.)
  * **Independent cross-check** — compares the live top-N momentum candidates'
    price / 52-week-high against a free-tier independent vendor
    (``SCREENER_INDEPENDENT_QUOTE_API_KEY``, process-local, never read from a
    file). This is NOT a CI gate: a network outage / missing key reports
    ``UNVERIFIED`` and the script still exits 0 for the cross-check section
    (FR-007). A real ``DIVERGES_UNFLAGGED`` or a seeded miss is what flips the
    written overall verdict to ``fail``.

Usage:
    python scripts/run_integrity_harness.py --as-of 2026-06-12 --out report.md
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.src.data.independent_quote import (  # noqa: E402
    build_default_independent_provider,
)
from backend.src.screening.integrity.harness import (  # noqa: E402
    HarnessReport,
    control_is_clean,
    cross_check,
    render_report,
    run_seeded_suite,
)


def _opt_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _live_snapshot_frame(as_of: str) -> tuple[pd.DataFrame, str]:
    """Run the live momentum screen and project its candidates into a contract-
    readable frame for the cross-check + seeded sections.

    Series-integrity (data-model §8) signals are defaulted safe here: until the
    US3 remediation populates them on the live snapshot, the series/identity
    invariants pass through, and value-domain / coherence / score invariants still
    catch the figure-level defects we seed. Returns (frame, data_as_of).
    """
    from backend.src import strategies as _strategies  # noqa: F401  (registration)
    from backend.src.screening import engine

    result = engine.run_strategy("midterm_52w_high_momentum", as_of_date=as_of)
    rows: List[dict] = []
    for c in result.candidates:
        close = _opt_float(c.entry)
        dist = _opt_float(c.dist_to_high)
        high = close * (1.0 + dist) if (close is not None and dist is not None) else None
        rows.append(
            {
                "ticker": c.ticker,
                "name": c.name,
                "sector": c.sector,
                "close": close,
                "52w_high": high,
                "dist_to_high": dist,
                "entry": close,
                "atr": _opt_float(getattr(c, "atr", None)),
                "stop_loss": _opt_float(c.stop_loss),
                "take_profit": _opt_float(c.take_profit),
                "vol_scalar": _opt_float(getattr(c, "vol_scalar", None)),
                "score": _opt_float(c.score),
                "return_12_1": _opt_float(c.return_12_1),
                # data-model §8 signals populated in Phase 5 (US3).
                "series_dates_ok": c.series_dates_ok,
                "series_max_session_move": c.series_max_session_move,
                "seam_consistent": c.seam_consistent,
                "seam_factor": c.seam_factor,
                "seam_overlap_found": getattr(c, "seam_overlap_found", True),
                "corporate_action_in_window": c.corporate_action_in_window,
                "adj_close_basis_used": c.adj_close_basis_used,
                "share_class_consistent": c.share_class_consistent,
            }
        )
    return pd.DataFrame(rows), result.data_as_of


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True, help="Snapshot date, e.g. 2026-06-12")
    parser.add_argument("--out", required=True, help="Path to write the report markdown")
    parser.add_argument("--top-n", type=int, default=10, help="Cross-check top-N cap")
    args = parser.parse_args(argv)

    from backend.src.strategies.midterm_52w_high_momentum import OUTPUT_CONTRACT

    try:
        snapshot, data_as_of = _live_snapshot_frame(args.as_of)
    except Exception as exc:  # no warm data / unexpected — report, don't crash CI
        print(f"[harness] could not build live snapshot: {exc}", file=sys.stderr)
        snapshot, data_as_of = pd.DataFrame(), args.as_of

    if snapshot.empty:
        print(
            "[harness] live screen returned no candidates; cannot run the harness "
            f"for as-of {args.as_of}.",
            file=sys.stderr,
        )
        return 0

    # Seeded regression (deterministic) — target a clean candidate when one exists.
    target = str(snapshot["ticker"].iloc[0])
    seeded = run_seeded_suite(snapshot, OUTPUT_CONTRACT, target_ticker=target)
    control_clean = control_is_clean(snapshot, OUTPUT_CONTRACT)

    # Independent cross-check (on demand, non-blocking). No key -> UNVERIFIED rows.
    provider = build_default_independent_provider()
    verdicts = cross_check(
        snapshot, OUTPUT_CONTRACT, provider, top_n=args.top_n
    )
    fetch_at = verdicts[0].independent_fetch_at if verdicts else None
    source = next(
        ("finnhub/alpha_vantage" for v in verdicts if v.independent_price is not None),
        "unavailable",
    )

    report = HarnessReport(
        snapshot_as_of=args.as_of,
        snapshot_id=data_as_of or args.as_of,
        independent_source=source,
        independent_fetch_at=fetch_at,
        seeded_results=seeded,
        control_clean=control_clean,
        cross_check_verdicts=verdicts,
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_report(report), encoding="utf-8")

    print(
        f"[harness] wrote {out_path} — seeded "
        f"{report.seeded_detected}/{len(seeded)} detected, "
        f"{report.diverges_unflagged} DIVERGES_UNFLAGGED, overall "
        f"{'pass' if report.overall_pass else 'fail'}."
    )
    # Cross-check failures are reported but do NOT fail the build (Decision 6); only
    # a seeded miss (a real regression in the detector) is worth a non-zero exit.
    return 0 if report.seeded_missed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
