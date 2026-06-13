"""Compute + cache the fixed reference-universe thresholds for the cross-sectional
GP / asset-growth gates (Novy-Marx / Cooper-Gulen-Schill). Run after a price/data
refresh so a name's top/bottom-half verdict is stable across the screen and
single-ticker analysis instead of flipping with the screened slice.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.src.screening.engine import refresh_reference_thresholds


def main() -> None:
    payload = refresh_reference_thresholds()
    print("Reference thresholds saved:")
    print(f"  universe_size : {payload['universe_size']}")
    print(f"  gp_threshold  : {payload['gp_threshold']}")
    print(f"  ag_threshold  : {payload['ag_threshold']}")
    print(f"  as_of         : {payload['as_of']}")


if __name__ == "__main__":
    main()
