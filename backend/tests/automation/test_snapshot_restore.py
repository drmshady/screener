from __future__ import annotations

from pathlib import Path

from scripts._restore_snapshot import resolve_restore_decision


def test_reports_restored_when_prior_data_tree_exists(tmp_path: Path) -> None:
    data_tree = tmp_path / "backend" / "data"
    data_tree.mkdir(parents=True)

    decision = resolve_restore_decision(
        extracted_data_tree=data_tree,
        extraction_succeeded=True,
        prior_image_available=True,
    )

    assert decision.outcome == "restored"
    assert decision.restored_path == data_tree


def test_missing_prior_image_fails_open_as_first_run(tmp_path: Path) -> None:
    decision = resolve_restore_decision(
        extracted_data_tree=tmp_path / "missing",
        extraction_succeeded=False,
        prior_image_available=False,
    )

    assert decision.outcome == "skipped"
    assert "first run" in decision.reason


def test_extraction_failure_fails_open_without_raising(tmp_path: Path) -> None:
    decision = resolve_restore_decision(
        extracted_data_tree=tmp_path / "missing",
        extraction_succeeded=False,
        prior_image_available=True,
    )

    assert decision.outcome == "skipped"
    assert "full refresh" in decision.reason
