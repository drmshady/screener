from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.src.lib.disclaimer import utc_now_iso

STOOQ_URL = "https://stooq.com/db/d/?b=d_us_txt"
DEST_ZIP = ROOT / "backend" / "data" / "prices" / "d_us_txt.zip"
EXTRACT_DIR = ROOT / "backend" / "data" / "prices" / "stooq"
MANIFEST_PATH = ROOT / "backend" / "data" / "manifest.json"


def _update_manifest(file_count: int) -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) if MANIFEST_PATH.exists() else {"sources": {}}
    manifest.setdefault("sources", {})["stooq"] = {
        "kind": "prices",
        "source_as_of": utc_now_iso(),
        "refresh_interval_days": 90,
        "source_url": STOOQ_URL,
        "last_file_count": file_count,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and extract the real Stooq US daily-bar bundle.")
    parser.add_argument("--skip-download", action="store_true", help="Extract an already downloaded ZIP.")
    args = parser.parse_args()

    DEST_ZIP.parent.mkdir(parents=True, exist_ok=True)
    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    if not args.skip_download:
        print(f"Downloading {STOOQ_URL} to {DEST_ZIP}...")
        urlretrieve(STOOQ_URL, DEST_ZIP)

    if not DEST_ZIP.exists():
        raise SystemExit(f"Missing {DEST_ZIP}; run without --skip-download first.")

    print(f"Extracting {DEST_ZIP} to {EXTRACT_DIR}...")
    with zipfile.ZipFile(DEST_ZIP, "r") as zip_ref:
        zip_ref.extractall(EXTRACT_DIR)

    file_count = len(list(EXTRACT_DIR.rglob("*.txt")))
    _update_manifest(file_count)
    print(f"Extracted {file_count} Stooq text files.")


if __name__ == "__main__":
    main()
