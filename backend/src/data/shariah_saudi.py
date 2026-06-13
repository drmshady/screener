"""Provisional Saudi (Tadawul) compliance source — Phase 16 (T170).

TEST DATA, NOT A RULING. The operator chose to treat every seeded Saudi name as
Shariah-compliant *for testing the market expansion only*. This labels the whole
Saudi starter universe compliant under the source name `saudi_all_compliant`,
clearly flagged as unverified. Replace later with an operator-provided compliant
list or the rule-based AAOIFI screen (T128-T132).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from .saudi_universe import saudi_universe
from .shariah_sources import DEFAULT_DB_PATH, DEFAULT_MANIFEST_PATH, replace_source_rows

SAUDI_SOURCE_NAME = "saudi_all_compliant"


def seed_saudi_all_compliant(
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    manifest_path: Path | str = DEFAULT_MANIFEST_PATH,
) -> int:
    today = date.today().isoformat()
    rows = [
        {
            "ticker": ticker,
            "source_name": SAUDI_SOURCE_NAME,
            "source_kind": "external",
            "source_as_of": today,
            "source_url": "",
        }
        for ticker in saudi_universe()
    ]
    return replace_source_rows(
        SAUDI_SOURCE_NAME,
        rows,
        db_path=db_path,
        manifest_path=manifest_path,
        manifest_metadata={
            "display_name": "Saudi (test — all compliant, UNVERIFIED)",
            "refresh_interval_days": 3650,
            "notes": (
                "TEST ONLY — every seeded Saudi name is labelled compliant for "
                "feasibility testing. NOT a Shariah ruling. Replace with an "
                "operator list or the AAOIFI rule-based screen before any real use."
            ),
        },
    )


if __name__ == "__main__":
    count = seed_saudi_all_compliant()
    print(f"Seeded {count} provisional Saudi compliance rows (TEST ONLY)")
