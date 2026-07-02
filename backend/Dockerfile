FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Runtime needs no compiler: every dependency installs from a prebuilt manylinux
# wheel (no sdist builds), so build-essential is pure image bloat (~350 MB+).
# Keep only curl for in-container debugging; the platform health check is HTTP.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml /tmp/backend-pyproject.toml
RUN python - <<'PY'
import subprocess
import sys
import tomllib

with open("/tmp/backend-pyproject.toml", "rb") as fh:
    project = tomllib.load(fh)["project"]

deps = list(project["dependencies"])
if not any(dep.lower().startswith("pyyaml") for dep in deps):
    deps.append("pyyaml>=6.0.2")

subprocess.check_call([sys.executable, "-m", "pip", "install", "--no-cache-dir", *deps])
PY

# Application source only (no tests, no local tooling).
COPY backend/pyproject.toml /app/backend/pyproject.toml
COPY backend/src /app/backend/src

# Read-only data snapshot — explicit scope so ONLY snapshot/data files enter the
# image and no key/secret file is ever bundled (FR-010, SC-008). Scope mirrors
# contracts/snapshot-publish.md: prices parquet, catalog.db (incl. backtest_runs),
# committed backtest artifacts, EDGAR slim cache, regime cache, calendars,
# reference thresholds, sector map, and the per-source manifest.
COPY backend/data/manifest.json /app/backend/data/manifest.json
COPY backend/data/catalog.db /app/backend/data/catalog.db
COPY backend/data/reference_thresholds.json /app/backend/data/reference_thresholds.json
COPY backend/data/econ_calendar.yaml /app/backend/data/econ_calendar.yaml
COPY backend/data/sic_to_sector.yaml /app/backend/data/sic_to_sector.yaml
COPY backend/data/prices /app/backend/data/prices
COPY backend/data/edgar_cache /app/backend/data/edgar_cache
COPY backend/data/backtests /app/backend/data/backtests
COPY backend/data/regime /app/backend/data/regime
COPY backend/data/halal_terminal_cache /app/backend/data/halal_terminal_cache
COPY backend/data/finbert_onnx /app/backend/data/finbert_onnx

EXPOSE 8000

CMD ["uvicorn", "backend.src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
