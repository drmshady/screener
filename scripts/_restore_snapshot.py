"""Prior-snapshot restore decision helpers for the daily publish chain.

The GitHub Actions runner starts from a clean checkout, so `backend/data/` has no
state for `ingest_daily` to increment from. The publish chain restores that tree
from the previously published image when possible, but this step is an efficiency
optimization only: first runs or extraction failures must fail open.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

RestoreOutcome = Literal["restored", "skipped"]


@dataclass(frozen=True)
class RestoreDecision:
    outcome: RestoreOutcome
    restored_path: Path | None
    reason: str


def resolve_restore_decision(
    *,
    extracted_data_tree: Path | None,
    extraction_succeeded: bool,
    prior_image_available: bool,
) -> RestoreDecision:
    """Report whether a prior data tree was restored.

    This function never raises. Missing images, failed extraction, and absent
    data trees are all documented skips so the caller can proceed with a full
    refresh rather than aborting the publish chain.
    """
    if not prior_image_available:
        return RestoreDecision(
            outcome="skipped",
            restored_path=None,
            reason="skipped (first run): no prior image was available",
        )
    if not extraction_succeeded:
        return RestoreDecision(
            outcome="skipped",
            restored_path=None,
            reason="skipped (restore failed): proceeding with a full refresh",
        )
    if extracted_data_tree is None or not extracted_data_tree.exists():
        return RestoreDecision(
            outcome="skipped",
            restored_path=None,
            reason="skipped (restore missing): extracted data tree was not found",
        )
    return RestoreDecision(
        outcome="restored",
        restored_path=extracted_data_tree,
        reason=f"restored prior data tree from {extracted_data_tree}",
    )
