from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pytest

from backend.src.data.saudi_universe import saudi_universe
from backend.src.screening.engine import (
    _compliant_universe,
    build_universe_snapshot,
    build_universe_snapshot_stooq,
)
from backend.src.shariah.lookup import normalize_shariah_overrides
from backend.src.strategies import midterm_52w_high_momentum as midterm
from backend.src.strategies._helpers.quality import passes_quality_screen


DEFAULT_SHARIAH_SOURCES = [
    "spus_holdings",
    "spwo_holdings",
    "spre_holdings",
    "spte_holdings",
    "halal_terminal",
]

GATE_ORDER = [
    "liquidity",
    "proximity",
    "trend",
    "volume",
    "quality",
    "gross_profitability",
    "asset_growth",
]


@dataclass(frozen=True)
class FrozenSnapshot:
    us_raw_tickers: list[str]
    us: pd.DataFrame
    us_prepared: pd.DataFrame
    us_data_as_of: str
    saudi_raw_tickers: list[str]
    saudi: pd.DataFrame
    saudi_prepared: pd.DataFrame
    saudi_data_as_of: str
    strong_sectors: set[str] | None
    gp_applied: bool
    ag_applied: bool


# Frozen *reference* inputs the validation must not corrupt. The live
# yfinance EOD store (`prices/parquet/`) is intentionally EXCLUDED: building a
# universe snapshot legitimately refreshes it, and `save_prices` stamps each
# row with a wall-clock `source_as_of` + pyarrow writes a fresh randomly-named
# partition file, so it is non-byte-stable by design. That cache churn does not
# affect screen/regime/sizing/backtest output (asserted separately by the
# determinism tests). The deep Stooq history under `prices/stooq*` stays frozen.
_FROZEN_COMPONENTS = {
    "backtests",
    "edgar_cache",
    "halal_terminal_cache",
    "raw",
    "catalog.db",
    "econ_calendar.yaml",
    "manifest.json",
    "sic_to_sector.yaml",
}
# Frozen price *reference* subtrees (deep history / bundles), guarded by size.
_FROZEN_PRICE_SUBTREES = (
    "prices/stooq",
    "prices/stooq_parquet",
    "prices/stooq_synthetic_delisted",
    "prices/saudi_parquet",
    "prices/d_us_txt.zip",
)
# Volatile, recomputed caches the validation is allowed to refresh.
_VOLATILE_PREFIXES = (
    "prices/parquet",  # live yfinance EOD store
    "cache",
    "regime",
)


def _is_frozen_reference(rel_posix: str, top: str) -> bool:
    if any(rel_posix == p or rel_posix.startswith(p + "/") for p in _VOLATILE_PREFIXES):
        return False
    if top in _FROZEN_COMPONENTS:
        return True
    return any(
        rel_posix == p or rel_posix.startswith(p + "/") for p in _FROZEN_PRICE_SUBTREES
    )


def _data_inventory_signature() -> tuple[tuple[str, int], ...]:
    root = Path("backend/data").resolve()
    out = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if not rel.parts:
            continue
        rel_posix = rel.as_posix()
        if _is_frozen_reference(rel_posix, rel.parts[0]):
            out.append((rel_posix, path.stat().st_size))
    return tuple(sorted(out))


@pytest.fixture(scope="session")
def frozen_snapshot() -> FrozenSnapshot:
    before = _data_inventory_signature()
    overrides = normalize_shariah_overrides({"active_sources": DEFAULT_SHARIAH_SOURCES})
    us_raw = _compliant_universe(overrides)
    us, us_data_as_of = build_universe_snapshot_stooq(us_raw)
    us_prepared, strong_sectors, gp_applied, ag_applied = midterm.prepare_universe_gates(us)

    saudi_raw = saudi_universe()
    saudi, saudi_data_as_of = build_universe_snapshot(saudi_raw)
    saudi_prepared, _, _, _ = midterm.prepare_universe_gates(saudi)

    yield FrozenSnapshot(
        us_raw_tickers=us_raw,
        us=us,
        us_prepared=us_prepared,
        us_data_as_of=us_data_as_of,
        saudi_raw_tickers=saudi_raw,
        saudi=saudi,
        saudi_prepared=saudi_prepared,
        saudi_data_as_of=saudi_data_as_of,
        strong_sectors=strong_sectors,
        gp_applied=gp_applied,
        ag_applied=ag_applied,
    )

    after = _data_inventory_signature()
    assert after == before, (
        "validation tests mutated FROZEN reference data under backend/data; the "
        "snapshot's reference inputs must stay read-only (the live yfinance EOD "
        "cache under prices/parquet is allowed to refresh and is excluded)"
    )


def hard_gate_funnel(snapshot: FrozenSnapshot) -> list[dict[str, int]]:
    df = snapshot.us_prepared.copy()
    vol_col = "volume_ratio_recent" if "volume_ratio_recent" in df.columns else "volume_ratio_50"
    stages: list[tuple[str, pd.Series]] = [
        ("liquidity", pd.Series(True, index=df.index)),
        ("proximity", df["dist_to_high"] <= midterm.PARAMETERS["proximity_pct"].default),
        ("trend", df["sma_200"].notna() & (df["close"] > df["sma_200"])),
        (
            "volume",
            df[vol_col].isna()
            | (df[vol_col] >= midterm.PARAMETERS["min_volume_ratio"].default),
        ),
        (
            "quality",
            df.apply(
                lambda row: passes_quality_screen(
                    row["debt_to_equity"],
                    row["fcf_ttm"],
                    midterm.PARAMETERS["max_debt_equity"].default,
                ),
                axis=1,
            ),
        ),
        ("gross_profitability", df["_gp_pass"]),
        ("asset_growth", df["_ag_pass"]),
    ]
    active = pd.Series(True, index=df.index)
    out = []
    for gate, mask in stages:
        active = active & mask
        out.append({"gate": gate, "survivors": int(active.sum())})
    return out


def first_rejecting_gate(row: pd.Series, snapshot: FrozenSnapshot) -> str | None:
    df = snapshot.us_prepared
    vol_col = "volume_ratio_recent" if "volume_ratio_recent" in df.columns else "volume_ratio_50"
    checks: list[tuple[str, bool]] = [
        ("proximity", bool(row["dist_to_high"] <= midterm.PARAMETERS["proximity_pct"].default)),
        ("trend", bool(pd.notna(row["sma_200"]) and row["close"] > row["sma_200"])),
        (
            "volume",
            bool(
                pd.isna(row[vol_col])
                or row[vol_col] >= midterm.PARAMETERS["min_volume_ratio"].default
            ),
        ),
        (
            "quality",
            passes_quality_screen(
                row["debt_to_equity"],
                row["fcf_ttm"],
                midterm.PARAMETERS["max_debt_equity"].default,
            ),
        ),
        ("gross_profitability", bool(row["_gp_pass"])),
        ("asset_growth", bool(row["_ag_pass"])),
    ]
    for gate, ok in checks:
        if not ok:
            return gate
    return None
