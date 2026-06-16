"""HarnessReport verdict semantics (feature 008).

A LIVE harness run legitimately carries genuine data-integrity flags in the
un-corrupted snapshot (e.g. a no-overlap seam-unverified name). Those are
findings to review, NOT a control false positive — they must not flip the
overall verdict to fail. SC-002 (no false positives on KNOWN-CLEAN data) is
gated separately by the seeded suite's clean-fixture control test.
"""
from __future__ import annotations

from backend.src.screening.integrity.harness import (
    HarnessReport,
    SeededDefectResult,
    render_report,
)


def _seeded(detected: bool) -> SeededDefectResult:
    return SeededDefectResult(
        defect_class="x",
        target_ticker="T",
        expected_family="series",
        detected=detected,
        fired_families=("series",) if detected else (),
    )


def _report(*, control_clean: bool, seeded_ok: bool) -> HarnessReport:
    return HarnessReport(
        snapshot_as_of="2026-06-12",
        snapshot_id="frozen",
        independent_source="unavailable",
        independent_fetch_at=None,
        seeded_results=[_seeded(seeded_ok)],
        control_clean=control_clean,
        cross_check_verdicts=[],
    )


def test_live_flags_do_not_fail_the_verdict():
    # Full seeded detection, no DIVERGES_UNFLAGGED, but the live snapshot carries
    # real flags (control_clean False) -> still a PASS.
    report = _report(control_clean=False, seeded_ok=True)
    assert report.overall_pass is True
    md = render_report(report)
    assert "Go:" in md
    assert "findings, not a gate failure" in md
    assert "**FAIL**" not in md  # no alarming false-positive verdict


def test_seeded_miss_still_fails():
    report = _report(control_clean=True, seeded_ok=False)
    assert report.overall_pass is False
    assert "No-go" in render_report(report)


def test_clean_baseline_reads_clean():
    report = _report(control_clean=True, seeded_ok=True)
    assert report.overall_pass is True
    assert "clean baseline" in render_report(report)
