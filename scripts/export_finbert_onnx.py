from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

MODEL_ID = "ProsusAI/finbert"
MODEL_REVISION = "main"
OUT_DIR = Path(__file__).resolve().parents[1] / "backend" / "data" / "finbert_onnx"


def main() -> int:
    model_path = OUT_DIR / "model.onnx"
    tokenizer_path = OUT_DIR / "tokenizer.json"
    if model_path.exists() and tokenizer_path.exists():
        print(f"FinBERT ONNX already present at {OUT_DIR}; skipping export.")
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # NOTE: the installed optimum ONNX exporter CLI has no --revision flag, so we
    # export from the model's default branch (MODEL_REVISION == "main", which is
    # the exporter default) and record the revision in export_metadata.json below.
    cmd = [
        sys.executable,
        "-m",
        "optimum.exporters.onnx",
        "--model",
        MODEL_ID,
        "--task",
        "text-classification",
        str(OUT_DIR),
    ]
    subprocess.check_call(cmd)
    (OUT_DIR / "export_metadata.json").write_text(
        json.dumps(
            {"model_id": MODEL_ID, "revision": MODEL_REVISION, "format": "onnx"},
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
