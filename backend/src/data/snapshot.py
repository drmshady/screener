"""Read-only data-snapshot integrity check for hosted deployment.

The hosted instance serves a snapshot baked into the backend image. Before the
platform routes traffic to a freshly published image it probes the health check,
which calls :func:`check_snapshot_integrity` to confirm the manifest parses and
every key store is present. A partial/corrupt snapshot therefore never receives
traffic (the atomic swap keeps the last good image serving), and a genuinely
absent snapshot surfaces as an explicit maintenance state rather than a partial
or crashing response (FR-006).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from ..lib import hosting

# Key stores that together make up a complete snapshot scope. Order is the
# reporting order; membership is what the health check enforces.
STORE_NAMES = ("manifest", "prices", "catalog", "edgar_cache", "calendars")


@dataclass(frozen=True)
class SnapshotIntegrity:
    ok: bool
    manifest_ok: bool
    present: dict[str, bool]
    missing: tuple[str, ...]


def _manifest_ok(root: Path) -> bool:
    path = root / "manifest.json"
    if not path.exists():
        return False
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return True


def _prices_ok(root: Path) -> bool:
    parquet_dir = root / "prices" / "parquet"
    if not parquet_dir.is_dir():
        return False
    return any(parquet_dir.rglob("*.parquet"))


def _catalog_ok(root: Path) -> bool:
    path = root / "catalog.db"
    if not path.exists():
        return False
    try:
        con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            tables = {
                row[0]
                for row in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        finally:
            con.close()
    except sqlite3.Error:
        return False
    # backtest_runs is part of the snapshot scope (hosted backtests are read
    # from committed runs, never recomputed in-host).
    return "backtest_runs" in tables


def _edgar_ok(root: Path) -> bool:
    cache_dir = root / "edgar_cache"
    if not cache_dir.is_dir():
        return False
    return any(cache_dir.glob("*.json"))


def _calendars_ok(root: Path) -> bool:
    return (root / "econ_calendar.yaml").exists()


def check_snapshot_integrity(root: Path | str | None = None) -> SnapshotIntegrity:
    """Validate that the read-only snapshot at ``root`` is complete.

    Performs no network calls and writes nothing. When ``root`` is omitted the
    hosted snapshot root is used.
    """
    base = Path(root) if root is not None else hosting.snapshot_root()
    present = {
        "manifest": _manifest_ok(base),
        "prices": _prices_ok(base),
        "catalog": _catalog_ok(base),
        "edgar_cache": _edgar_ok(base),
        "calendars": _calendars_ok(base),
    }
    missing = tuple(name for name in STORE_NAMES if not present[name])
    return SnapshotIntegrity(
        ok=not missing,
        manifest_ok=present["manifest"],
        present=present,
        missing=missing,
    )
