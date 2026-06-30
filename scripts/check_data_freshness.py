"""Non-fatal data-freshness warning for the publish chain (WS3).

The Halal Terminal Shariah source has a 90-day refresh deadline that is enforced
at *runtime* on the host (shariah/lookup.py): once the baked snapshot's
`source_as_of` crosses the interval the compliant universe is flagged stale, and
the cloud cannot self-heal it without HALAL_TERMINAL_API_KEY. This script reads
the manifest and warns the owner *before* the deadline (and loudly once past it),
writing to stdout and the GitHub Actions step summary. It NEVER fails the build:
stale compliance is a warning, not a corrupt snapshot.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.src.shariah.refresh_cadence import freshness_status

MANIFEST_PATH = ROOT / "backend" / "data" / "manifest.json"

# Sources with a hard runtime staleness deadline worth warning about early.
WATCHED = {"halal_terminal": 90}
WARN_WITHIN_DAYS = 14


def _parse_dt(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _emit(line: str) -> None:
    print(line)
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def main() -> int:
    if not MANIFEST_PATH.exists():
        print(f"check_data_freshness: no manifest at {MANIFEST_PATH}; skipping.")
        return 0
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    sources = manifest.get("sources", {})
    now = datetime.now(timezone.utc)

    any_warning = False
    for name, interval in WATCHED.items():
        meta = sources.get(name)
        source_as_of = _parse_dt(meta.get("source_as_of")) if meta else None
        status = freshness_status(
            now, source_as_of, interval_days=interval, warn_within_days=WARN_WITHIN_DAYS
        )
        if status.status == "fresh":
            print(f"check_data_freshness: {name} OK ({status.reason}).")
            continue
        any_warning = True
        prefix = "STALE" if status.status == "stale" else "DUE SOON"
        _emit(
            f"::warning title=Compliance data {prefix}::{name} {status.reason}. "
            "Re-run the Halal Terminal refresh (needs HALAL_TERMINAL_API_KEY) and "
            "republish so the hosted compliant universe does not bake stale."
        )

    if not any_warning:
        print("check_data_freshness: all watched sources are within their refresh deadline.")
    # Always succeed: this is a heads-up, never a publish gate.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
